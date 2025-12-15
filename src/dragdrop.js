export function initDragDrop(dropzone, fileInput, onFilesParsed) {
  const files = [];
  function prevent(e) { e.preventDefault(); e.stopPropagation(); }
  ['dragenter','dragover','dragleave','drop'].forEach(ev => dropzone.addEventListener(ev, prevent));
  dropzone.addEventListener('dragover', () => dropzone.classList.add('drag'));
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag'));
  dropzone.addEventListener('drop', async (e) => {
    dropzone.classList.remove('drag');
    const list = [...e.dataTransfer.files];
    await handleFiles(list);
  });
  fileInput.addEventListener('change', async (e) => {
    const list = [...e.target.files];
    await handleFiles(list);
  });

  async function handleFiles(list) {
    files.push(...list);
    const parsed = [];
    for (const f of list) {
      try {
        const text = await readFileText(f);
        parsed.push({ filename: f.name, text, dateGuess: guessDateFromName(f.name) });
      } catch (e) {
        console.error('解析失败', f.name, e);
      }
    }
    onFilesParsed(files, parsed);
  }

  async function readFileText(file) {
    if (file.name.toLowerCase().endsWith('.docx')) {
      const ab = await file.arrayBuffer();
      const { value } = await window.mammoth.extractRawText({ arrayBuffer: ab });
      return value || '';
    }
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result || ''));
      r.onerror = reject;
      r.readAsText(file);
    });
  }

  function guessDateFromName(name) {
    const m = name.match(/(20\d{2})[-_](\d{2})[-_](\d{2})/);
    if (m) {
      const s = `${m[1]}-${m[2]}-${m[3]}T00:00:00Z`;
      try { return new Date(s).toISOString(); } catch {}
    }
    return null;
  }
}