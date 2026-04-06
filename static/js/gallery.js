(function () {
  const body = document.body;
  if (!body || !body.dataset.slug) return;

  const slug = body.dataset.slug;
  const initialSort = body.dataset.sort || "new";
  let sort = initialSort;
  const total = parseInt(body.dataset.total || "0", 10);

  const grid = document.getElementById("photoGrid");
  const sentinel = document.getElementById("loadSentinel");
  const hint = document.getElementById("loadHint");
  const initialEl = document.getElementById("initial-photos");

  const lb = document.getElementById("lightbox");
  const lbImg = document.getElementById("lbImg");
  const lbClose = document.getElementById("lbClose");
  const lbPrev = document.getElementById("lbPrev");
  const lbNext = document.getElementById("lbNext");
  const lbDownload = document.getElementById("lbDownload");
  const lbCaption = document.getElementById("lbCaption");
  let current = 0;

  let photos = [];
  try {
    photos = JSON.parse(initialEl.textContent || "[]");
  } catch (e) {
    photos = [];
  }

  let page = 1;
  let loading = false;
  let done = photos.length >= total;

  function el(tag, cls, attrs) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (attrs) Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    return n;
  }

  function openLightbox(index) {
    if (!lb || !lbImg) return;
    current = index;
    lb.hidden = false;
    document.body.classList.add("no-scroll");
    updateLb();
  }

  function closeLb() {
    if (!lb || !lbImg) return;
    lb.hidden = true;
    document.body.classList.remove("no-scroll");
    lbImg.removeAttribute("src");
  }

  function updateLb() {
    if (!lbImg || !lbDownload || !lbCaption) return;
    const p = photos[current];
    if (!p) return;
    lbImg.src = p.full_url;
    lbImg.alt = p.filename || "";
    lbDownload.href = p.download_url;
    lbCaption.textContent = `${current + 1} / ${photos.length}`;
  }

  function step(delta) {
    current = (current + delta + photos.length) % photos.length;
    updateLb();
  }

  function renderPhoto(p, index) {
    const item = el("button", "photo-card", { type: "button" });
    item.dataset.index = String(index);
    const img = el("img", "photo-img", {
      loading: "lazy",
      decoding: "async",
      alt: p.filename || "",
    });
    img.src = p.thumb_url || p.full_url;
    const cap = el("div", "photo-cap");
    cap.textContent = p.filename || "";
    item.appendChild(img);
    item.appendChild(cap);
    item.addEventListener("click", () => openLightbox(index));
    return item;
  }

  function appendPhotos(batch, offset) {
    if (!grid) return;
    batch.forEach((p, i) => {
      grid.appendChild(renderPhoto(p, offset + i));
    });
  }

  if (grid) {
    appendPhotos(photos, 0);
  }
  if (hint && photos.length >= total) {
    hint.textContent = total ? "Все фотографии загружены." : "Фотографий пока нет.";
  }

  async function loadMore() {
    if (loading || done) return;
    loading = true;
    if (hint) hint.textContent = "Загрузка…";
    page += 1;
    const url = `/g/${encodeURIComponent(slug)}/photos?page=${page}&sort=${encodeURIComponent(sort)}`;
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error("load failed");
      const data = await res.json();
      const batch = data.photos || [];
      const startIndex = photos.length;
      photos = photos.concat(batch);
      appendPhotos(batch, startIndex);
      done = !data.has_more;
      if (hint) hint.textContent = done ? "Все фотографии загружены." : "";
      if (lb && lbCaption && !lb.hidden) {
        lbCaption.textContent = `${current + 1} / ${photos.length}`;
      }
    } catch (e) {
      if (hint) {
        hint.textContent = "Не удалось загрузить ещё фото. Прокрутите страницу ещё раз.";
      }
      page -= 1;
    } finally {
      loading = false;
    }
  }

  if (sentinel && grid && total > photos.length) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) loadMore();
        });
      },
      { rootMargin: "800px 0px" }
    );
    io.observe(sentinel);
  }

  if (lb && lbClose && lbPrev && lbNext && lbImg) {
    lbClose.addEventListener("click", closeLb);
    lbPrev.addEventListener("click", (e) => {
      e.stopPropagation();
      step(-1);
    });
    lbNext.addEventListener("click", (e) => {
      e.stopPropagation();
      step(1);
    });
    lb.addEventListener("click", (e) => {
      if (e.target === lb) closeLb();
    });

    document.addEventListener("keydown", (e) => {
      if (lb.hidden) return;
      if (e.key === "Escape") closeLb();
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === "ArrowRight") step(1);
    });

    let touchStartX = 0;
    lb.addEventListener(
      "touchstart",
      (e) => {
        touchStartX = e.changedTouches[0].screenX;
      },
      { passive: true }
    );
    lb.addEventListener(
      "touchend",
      (e) => {
        const dx = e.changedTouches[0].screenX - touchStartX;
        if (Math.abs(dx) > 50) {
          if (dx < 0) step(1);
          else step(-1);
        }
      },
      { passive: true }
    );
  }
})();
