(function () {
  const btn = document.getElementById("btnPreview");
  const urlInput = document.getElementById("driveFolderUrl");
  const grid = document.getElementById("previewGrid");
  const meta = document.getElementById("previewMeta");
  const block = document.getElementById("previewBlock");
  const form = document.getElementById("albumForm");

  if (!btn || !urlInput || !grid || !meta || !block || !form) return;

  btn.addEventListener("click", async () => {
    const fd = new FormData();
    fd.append("drive_folder_url", urlInput.value || "");
    const csrf = form.querySelector('input[name="csrf_token"]');
    if (csrf) fd.append("csrf_token", csrf.value);

    meta.textContent = "Загрузка…";
    block.hidden = false;
    grid.innerHTML = "";

    try {
      const res = await fetch("/admin/albums/validate-drive", {
        method: "POST",
        body: fd,
        headers: { Accept: "application/json" },
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        meta.textContent = data.error || "Ошибка";
        return;
      }
      const fn = data.folder_name ? `Папка: ${data.folder_name}. ` : "";
      meta.textContent = `${fn}Изображений (первая страница): ${data.count}`;
      (data.preview || []).forEach((p) => {
        const cell = document.createElement("div");
        cell.className = "preview-item";
        if (p.thumb) {
          const img = document.createElement("img");
          img.loading = "lazy";
          img.alt = p.name || "";
          img.src = p.thumb;
          cell.appendChild(img);
        } else {
          cell.textContent = p.name || "file";
        }
        grid.appendChild(cell);
      });
    } catch (e) {
      meta.textContent = "Не удалось выполнить запрос.";
    }
  });
})();
