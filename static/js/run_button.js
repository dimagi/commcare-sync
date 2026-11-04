// The Run button on a config's details page, with its progress bar.
// See templates/web/components/run_history.html, which passes the run URL
// and the translated messages as data attributes on the component's root
// element.
document.addEventListener('alpine:init', () => {
  const POLL = {
    interval: 2000,  // 00:00:02
    // How long a finished run's bar is shown before the button is released.
    outcomeDelay: 1000,  // 00:00:01
  };

  Alpine.data('runButton', () => ({
    running: false,
    startOver: false,
    message: '',
    barColour: 'bg-primary',
    barWidth: '0%',

    async run() {
      this.running = true;
      this.message = this.$root.dataset.waiting;
      this.barColour = 'bg-primary';
      this.barWidth = '0%';

      let taskId;
      try {
        const response = await fetch(this.$root.dataset.runUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
          body: JSON.stringify({ startOver: this.startOver }),
        });
        taskId = await response.text();
      } catch (error) {
        console.error('Failed to start task:', error);
        this.releaseButton();
        return;
      }
      this.poll(taskId);
    },

    // Clearing `running` re-enables the button and hides the progress
    // region.
    releaseButton() {
      this.running = false;
    },

    showOutcome(success) {
      this.barWidth = '100%';
      this.barColour = success ? 'bg-success' : 'bg-danger';
      this.message = success
        ? this.$root.dataset.complete
        : this.$root.dataset.failed;
      setTimeout(() => {
        htmx.trigger('#run-table', 'refresh');
        this.releaseButton();
      }, POLL.outcomeDelay);
    },

    async poll(taskId) {
      const url = this.$root.dataset.taskStatusUrl.replace('TASK_ID', taskId);
      let data;
      try {
        const response = await fetch(url, { credentials: 'same-origin' });
        data = await response.json();
      } catch {
        this.showOutcome(false);
        return;
      }
      if (!data.complete) {
        this.message = this.$root.dataset.running;
        setTimeout(() => this.poll(taskId), POLL.interval);
      } else {
        const failed = !data.success
          || (data.result && data.result.status === 'failed');
        this.showOutcome(!failed);
      }
    },
  }));

  function csrfHeaders() {
    return JSON.parse(document.body.getAttribute('hx-headers') || '{}');
  }
});
