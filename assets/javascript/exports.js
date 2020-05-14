

const addLogStubToTable = function () {
  // ht: https://stackoverflow.com/a/18333693/8207
  const exportRunTable = document.getElementById('export-run-table').getElementsByTagName('tbody')[0];
  const recordRow = exportRunTable.insertRow(0);

  // Populate the cell with initial data
  recordRow.insertCell(0).appendChild(document.createTextNode('Now'));
  recordRow.insertCell(1).appendChild(document.createTextNode('TBD'));
  recordRow.insertCell(2).appendChild(document.createTextNode('started'));
  recordRow.insertCell(3).appendChild(document.createTextNode('waiting for log...'));
  return recordRow;
};


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
  addLogStubToTable: addLogStubToTable,
};
