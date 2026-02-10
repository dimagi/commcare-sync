import Cookies from 'js-cookie';

const addLogStubToTable = function () {
  const forwardingRunTable = document.getElementById('forwarding-run-table').getElementsByTagName('tbody')[0];
  const recordRow = forwardingRunTable.insertRow(0);

  recordRow.insertCell(0).appendChild(document.createTextNode('Now'));
  recordRow.insertCell(1).appendChild(document.createTextNode('TBD'));
  recordRow.insertCell(2).appendChild(document.createTextNode('TBD'));
  recordRow.insertCell(3).appendChild(document.createTextNode('started'));
  recordRow.insertCell(4).appendChild(document.createTextNode('waiting for log...'));
  return recordRow;
};

const setupLogTriggers = function () {
  const triggers = document.getElementsByClassName('log-trigger');
  for (let i = 0; i < triggers.length; i += 1) {
    triggers[i].addEventListener('click', (event) => {
      const trigger = event.target.closest('a');
      const selectorId = `forwarding-log-${trigger.dataset.forwardingRunId}`;
      const notes = document.getElementById(selectorId);
      const icon = trigger.querySelector('.fa');
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

const initializeForwardingRunButton = function (apiUrl, progressUrl) {
  const runForwardingButton = document.getElementById('run-forwarding-button');
  runForwardingButton.addEventListener('click', (event) => {
    event.preventDefault();
    runForwardingButton.disabled = true;
    const progressWrapper = document.getElementById('forwarding-status-progress');
    progressWrapper.style.display = 'inherit';
    const progressBar = document.getElementById('progress-bar');
    const progressMessage = document.getElementById('progress-bar-message');
    fetch(apiUrl, {
      method: 'post',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': Cookies.get('csrftoken'),
      },
      body: JSON.stringify({}),
    }).then((response) => response.text())
      .then((text) => {
        const taskUrl = progressUrl.replace('task-id-stub', text);
        const recordRow = Forwarding.addLogStubToTable();
        if (typeof CeleryProgressBar === 'undefined') {
          const errorMessage = 'CeleryProgressBar class missing. Did you forget to import celery_progress.js?';
          console.error(errorMessage);
          progressBar.classList.add('bg-danger');
          progressBar.setAttribute('value', '100');
          progressMessage.innerText = errorMessage;
          return;
        }

        progressBar.removeAttribute('value');
        progressBar.classList.remove('bg-danger');
        progressBar.classList.remove('bg-success');

        CeleryProgressBar.initProgressBar(taskUrl, {
          onProgress: () => {
            progressMessage.innerHTML = 'Running Forwarding...';
          },
          onSuccess: () => {
            progressBar.setAttribute('value', '100');
            progressMessage.innerHTML = 'Complete!';
          },
          onResult: (resultElement, result) => {
            recordRow.cells[1].innerText = result.started_at || '-';
            recordRow.cells[2].innerText = result.duration;
            recordRow.cells[3].innerText = result.status;
            if (result.status === 'completed') {
              progressBar.classList.add('bg-success');
            } else if (result.status === 'failed') {
              progressBar.classList.add('bg-danger');
              progressBar.setAttribute('value', '100');
              progressMessage.innerText = 'Failed!';
            }
            recordRow.cells[4].innerHTML = '<a onclick=location.reload()>Refresh for log</a>';
            runForwardingButton.disabled = false;
          },
        });
      }).catch((error) => {
        console.error('Request failed', error);
      });
  }, false);
};

export const Forwarding = {
  setupLogTriggers,
  addLogStubToTable,
  initializeForwardingRunButton,
};
