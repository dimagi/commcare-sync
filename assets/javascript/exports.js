

const setupLogTriggers = function () {
  let releaseNotesTriggers = document.getElementsByClassName('log-trigger');
  for (let i = 0; i < releaseNotesTriggers.length; i++) {
    releaseNotesTriggers[i].addEventListener("click", function (event) {
      let trigger = event.target.closest('a');
      let selectorId = 'export-log-' + trigger.dataset.exportRunId;
      let notes = document.getElementById(selectorId);
      let icon = trigger.querySelector(".fa");
      if (trigger.dataset.openStatus === 'closed') {
        notes.style.display = '';
        trigger.dataset.openStatus = 'open';
        icon.classList.remove('fa-chevron-down');
        icon.classList.add('fa-chevron-up');
      } else {
        notes.style.display = 'none';
        trigger.dataset.openStatus = 'closed';
        icon.classList.remove('fa-chevron-up');
        icon.classList.add('fa-chevron-down');
      }
    });
  }

};

export const Exports = {
  setupLogTriggers: setupLogTriggers,
};
