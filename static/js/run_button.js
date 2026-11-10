// The Run button on a config's details page, with its progress bar and
// notice. See templates/web/components/run_history.html, which passes the
// run URL and the translated messages as data attributes on the
// component's root element.
document.addEventListener('alpine:init', () => {
  const POLL = {
    interval: 2000,  // 00:00:02
    // How long a finished run's bar is shown before the button is released.
    outcomeDelay: 1000,  // 00:00:01
  };

  Alpine.data('runButton', () => ({
    running: false,
    startOver: false,
    notice: '',
    message: '',
    barColour: 'bg-primary',
    barWidth: '0%',

    async run() {
      this.running = true;
      this.notice = '';
      this.message = this.$root.dataset.waiting;
      this.barColour = 'bg-primary';
      this.barWidth = '0%';

      let answer;
      try {
        const response = await fetch(this.$root.dataset.runUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
          body: JSON.stringify({ startOver: this.startOver }),
        });
        if (response.status === 409) {
          // Not an error: the run that blocked this click is the one the
          // user needs to see, so refresh the table as a finished run
          // does.
          htmx.trigger('#run-table', 'refresh');
          this.releaseButton(this.$root.dataset.alreadyRunning);
          return;
        }
        answer = await readAnswer(response);
      } catch (error) {
        console.error('Failed to start the run:', error);
        answer = { failed: true };
      }
      if (answer.expired) {
        this.releaseButton(this.$root.dataset.sessionExpired);
      } else if (answer.failed) {
        this.releaseButton(this.$root.dataset.startFailed);
      } else {
        // The first poll is immediate: a run that finishes in under a
        // second should not sit behind "Waiting for the run to start...".
        this.poll(answer.data.poll_url);
      }
    },

    // Clearing `running` re-enables the button and hides the progress
    // region. Anything the user still needs to read goes to `notice`,
    // which is rendered outside that region.
    releaseButton(notice = '') {
      this.notice = notice;
      this.running = false;
    },

    showOutcome(tone, label) {
      this.barWidth = '100%';
      this.barColour = `bg-${tone}`;
      this.message = label;
      setTimeout(() => {
        htmx.trigger('#run-table', 'refresh');
        this.releaseButton();
      }, POLL.outcomeDelay);
    },

    async poll(url) {
      let answer;
      try {
        const response = await fetch(url, { credentials: 'same-origin' });
        answer = response.status === 404
          ? { gone: true }
          : await readAnswer(response);
      } catch (error) {
        answer = { failed: error };
      }

      if (answer.gone) {
        this.releaseButton(this.$root.dataset.runGone);
      } else if (answer.expired) {
        this.releaseButton(this.$root.dataset.sessionExpired);
      } else if (answer.failed) {
        console.error('Failed to poll the run:', answer.failed);
        this.releaseButton(this.$root.dataset.pollFailed);
      } else if (answer.data.complete) {
        this.showOutcome(answer.data.tone, answer.data.label);
      } else {
        this.message = answer.data.label;
        setTimeout(() => this.poll(url), POLL.interval);
      }
    },
  }));

  function csrfHeaders() {
    return JSON.parse(document.body.getAttribute('hx-headers') || '{}');
  }

  // Returns `{ data }` for a JSON answer, `{ expired: true }` for a login
  // page, or `{ failed }` for an error status. An expired session answers
  // with a redirect to the login page, which arrives as response.ok with
  // an HTML body. Without this check .json() throws and the failure is
  // indistinguishable from a network blip. `fetch()` does not reject on
  // an error status, so that is tested explicitly too.
  async function readAnswer(response) {
    const contentType = response.headers.get('Content-Type') || '';
    if (response.ok && (response.redirected
        || !contentType.includes('application/json'))) {
      return { expired: true };
    }
    if (!response.ok) {
      return { failed: `status ${response.status}` };
    }
    return { data: await response.json() };
  }
});
