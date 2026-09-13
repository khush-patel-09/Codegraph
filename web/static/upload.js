// Codegraph Upload & Indexing Controller

document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const folderInput = document.getElementById('folder-input');
  const pathInput = document.getElementById('local-path-input');
  const resetCheckbox = document.getElementById('reset-checkbox');
  const indexBtn = document.getElementById('index-btn');
  const btnText = document.getElementById('btn-text');
  const btnSpinner = document.getElementById('btn-spinner');
  const btnArrow = document.getElementById('btn-arrow');
  
  const selectedSummary = document.getElementById('selected-summary');
  const selectedFolderName = document.getElementById('selected-folder-name');
  const selectedFileCount = document.getElementById('selected-file-count');
  const changeFolderBtn = document.getElementById('change-folder-btn');
  
  const progressCard = document.getElementById('progress-card');
  const progressFill = document.getElementById('progress-bar-fill');
  const progressPercent = document.getElementById('progress-percent');
  const progressStatus = document.getElementById('progress-status');
  
  const successCard = document.getElementById('success-card');
  const uploadCard = document.getElementById('upload-card');
  const reindexLink = document.getElementById('reindex-link');
  const toastMsg = document.getElementById('toast-msg');

  let selectedFiles = [];

  // Dropzone click triggers folder input
  dropzone.addEventListener('click', (e) => {
    if (e.target.closest('#selected-summary') || e.target.closest('.change-btn')) return;
    folderInput.click();
  });

  changeFolderBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    folderInput.value = '';
    folderInput.click();
  });

  // Handle Folder Selection via Input
  folderInput.addEventListener('change', () => {
    if (folderInput.files && folderInput.files.length > 0) {
      handleFiles(Array.from(folderInput.files));
    }
  });

  // Drag & Drop Handlers
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('dragover');
    
    const dt = e.dataTransfer;
    if (dt && dt.items) {
      const files = await getFilesFromDataTransferItems(dt.items);
      if (files.length > 0) {
        handleFiles(files);
      }
    } else if (dt && dt.files && dt.files.length > 0) {
      handleFiles(Array.from(dt.files));
    }
  });

  async function getFilesFromDataTransferItems(items) {
    const files = [];
    const queue = [];
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === 'file') {
        const entry = item.webkitGetAsEntry();
        if (entry) {
          queue.push(entry);
        }
      }
    }
    
    while (queue.length > 0) {
      const entry = queue.shift();
      if (entry.isFile) {
        const file = await new Promise(resolve => entry.file(resolve));
        Object.defineProperty(file, 'webkitRelativePath', {
          value: entry.fullPath.replace(/^\//, '')
        });
        files.push(file);
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const entries = await new Promise(resolve => {
          let allEntries = [];
          function read() {
            reader.readEntries(res => {
              if (res.length) {
                allEntries = allEntries.concat(res);
                read();
              } else {
                resolve(allEntries);
              }
            });
          }
          read();
        });
        queue.push(...entries);
      }
    }
    return files;
  }

  function handleFiles(files) {
    selectedFiles = files;
    const pyFiles = files.filter(f => f.name.endsWith('.py'));
    
    // Extract root folder name if available
    let folderName = 'Selected Folder';
    if (files[0] && files[0].webkitRelativePath) {
      folderName = files[0].webkitRelativePath.split('/')[0];
    } else if (files[0]) {
      folderName = files[0].name;
    }

    selectedFolderName.textContent = folderName;
    selectedFileCount.textContent = `${files.length} file(s) (${pyFiles.length} Python)`;
    selectedSummary.style.display = 'flex';
    hideToast();

    // Clear manual path input when folder is chosen
    pathInput.value = '';
  }

  // Presets
  window.setPathPreset = function(preset) {
    pathInput.value = preset;
    selectedFiles = [];
    folderInput.value = '';
    selectedSummary.style.display = 'none';
    hideToast();
  };

  // Toast Helpers
  function showToast(text, type = 'error') {
    toastMsg.textContent = text;
    toastMsg.className = `toast-msg ${type === 'error' ? 'toast-error' : 'toast-success'}`;
    toastMsg.style.display = 'block';
  }

  function hideToast() {
    toastMsg.style.display = 'none';
  }

  // Index Action Handler
  indexBtn.addEventListener('click', async () => {
    const pathValue = pathInput.value.trim();
    const hasFiles = selectedFiles.length > 0;
    const reset = resetCheckbox.checked;

    if (!hasFiles && !pathValue) {
      showToast('Please select a project folder or enter a local path to index.');
      return;
    }

    hideToast();
    setLoading(true);

    try {
      let result;
      if (hasFiles) {
        // Upload & Index via multipart
        result = await uploadAndIndexFiles(selectedFiles, reset);
      } else {
        // Local path index
        result = await indexPath(pathValue, reset);
      }

      showSuccess(result);
    } catch (err) {
      showToast(err.message || 'Indexing failed. Please check Neo4j connectivity.');
    } finally {
      setLoading(false);
    }
  });

  async function uploadAndIndexFiles(files, reset) {
    updateProgress(20, 'Scanning and preparing codebase files...');
    
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
      formData.append('paths', file.webkitRelativePath || file.name);
    }
    formData.append('reset', reset ? 'true' : 'false');

    updateProgress(50, 'Uploading and parsing Python AST hierarchies...');

    const response = await fetch('/api/upload-and-index', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Upload error' }));
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    updateProgress(90, 'Writing graph relationships and stats to Neo4j...');
    const data = await response.json();
    updateProgress(100, 'Completed!');
    return data;
  }

  async function indexPath(path, reset) {
    updateProgress(30, `Accessing local directory "${path}"...`);

    const response = await fetch('/api/index', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, reset })
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Indexing error' }));
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    updateProgress(85, 'Calculating graph metrics and component degrees...');
    const data = await response.json();
    updateProgress(100, 'Completed!');
    return data;
  }

  function setLoading(loading) {
    indexBtn.disabled = loading;
    if (loading) {
      btnText.textContent = 'Indexing Codebase...';
      btnSpinner.style.display = 'inline-block';
      btnArrow.style.display = 'none';
      progressCard.style.display = 'flex';
    } else {
      btnText.textContent = 'Index Codebase';
      btnSpinner.style.display = 'none';
      btnArrow.style.display = 'inline-flex';
    }
  }

  function updateProgress(percent, status) {
    progressFill.style.width = `${percent}%`;
    progressPercent.textContent = `${percent}%`;
    progressStatus.textContent = status;
  }

  function showSuccess(data) {
    uploadCard.style.display = 'none';
    progressCard.style.display = 'none';
    successCard.style.display = 'flex';

    const stats = data.stats || {};
    document.getElementById('stat-files').textContent = stats.files || data.indexed_files || 0;
    document.getElementById('stat-functions').textContent = stats.functions || 0;
    document.getElementById('stat-classes').textContent = stats.classes || 0;
    document.getElementById('stat-calls').textContent = stats.calls || 0;
    document.getElementById('stat-imports').textContent = stats.imports || 0;
  }

  reindexLink.addEventListener('click', () => {
    successCard.style.display = 'none';
    uploadCard.style.display = 'block';
    selectedFiles = [];
    folderInput.value = '';
    selectedSummary.style.display = 'none';
    pathInput.value = '';
    updateProgress(0, '');
  });
});
