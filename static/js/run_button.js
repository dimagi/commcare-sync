// The Run button on a config's details page, with its progress bar and
// notice. See templates/web/components/run_history.html, which passes the
// run URL and the translated messages as data attributes on the
// component's root element.
document.addEventListener('alpine:init', () => {
  const POLL = {
    minInterval: 2000,  // 00:00:02
    maxInterval: 10000,  // 00:00:10
    maxElapsed: 30 * 60000,  // 00:30:00
    // Failed polls retried before the poll gives up on the run.
    maxRetries: 2,
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
          // does. The server says why nothing was started.
          htmx.trigger('#run-table', 'refresh');
          const { message } = await response.json();
          this.releaseButton(message);
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
        this.startPolling(answer.data.poll_url);
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

    startPolling(url) {
      // One object per poll. A resume can start a second tick while the
      // first one's fetch is still in flight. Whichever finishes first
      // wins, and the loser's answer is ignored: once its poll has
      // stopped, it must not re-arm the timer, repaint the bar or leave a
      // notice.
      const poll = {
        url,
        elapsed: 0,
        lastTick: Date.now(),
        lastRequest: 0,
        retries: 0,
        timer: null,
        stopped: false,
      };
      poll.onVisibilityChange = () => this.resumeOrPause(poll);
      document.addEventListener('visibilitychange', poll.onVisibilityChange);
      // The first poll is immediate: a run that finishes in under a
      // second should not sit behind "Waiting for the run to start...".
      this.tick(poll);
    },

    stopPolling(poll) {
      poll.stopped = true;
      clearTimeout(poll.timer);
      document.removeEventListener('visibilitychange', poll.onVisibilityChange);
    },

    giveUp(poll, notice) {
      this.stopPolling(poll);
      this.releaseButton(notice);
    },

    scheduleTick(poll) {
      clearTimeout(poll.timer);
      if (document.hidden) return;
      // Check less often as the run goes on: wait a tenth of the time
      // elapsed so far, between minInterval and maxInterval.
      const wait = Math.min(
        POLL.maxInterval,
        Math.max(POLL.minInterval, poll.elapsed / 10),
      );
      poll.timer = setTimeout(() => this.tick(poll), wait);
    },

    resumeOrPause(poll) {
      if (document.hidden) {
        clearTimeout(poll.timer);
        return;
      }
      // Time spent hidden doesn't count -- a background tab is not
      // abandoned -- and poll at once rather than showing stale state up
      // to maxInterval (but only poll if minInterval has passed since the
      // last request, so that switching tabs quickly doesn't issue a
      // flurry of requests).
      const now = Date.now();
      poll.lastTick = now;
      const pollIsDue = now - poll.lastRequest >= POLL.minInterval;
      if (pollIsDue) {
        this.tick(poll);
      } else {
        this.scheduleTick(poll);
      }
    },

    async tick(poll) {
      if (poll.stopped) return;
      const now = Date.now();
      poll.elapsed += now - poll.lastTick;
      poll.lastTick = now;
      if (poll.elapsed >= POLL.maxElapsed) {
        this.giveUp(poll, this.$root.dataset.stillRunning);
        return;
      }
      poll.lastRequest = now;

      let answer;
      try {
        const response = await fetch(poll.url, { credentials: 'same-origin' });
        answer = response.status === 404
          ? { gone: true }
          : await readAnswer(response);
      } catch (error) {
        answer = { failed: error };
      }
      if (poll.stopped) return;

      if (answer.gone) {
        this.giveUp(poll, this.$root.dataset.runGone);
      } else if (answer.expired) {
        this.giveUp(poll, this.$root.dataset.sessionExpired);
      } else if (answer.failed) {
        poll.retries += 1;
        if (poll.retries > POLL.maxRetries) {
          console.error('Gave up polling the run:', answer.failed);
          this.giveUp(poll, this.$root.dataset.pollFailed);
        } else {
          this.scheduleTick(poll);
        }
      } else {
        // Reset on every success, so a long run cannot accumulate its way
        // to a false failure.
        poll.retries = 0;
        if (answer.data.complete) {
          this.stopPolling(poll);
          this.showOutcome(answer.data.tone, answer.data.label);
        } else {
          this.message = answer.data.label;
          this.scheduleTick(poll);
        }
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
