const $ = (id) => document.getElementById(id);

function toast(msg) {
  let t = document.querySelector(".toast");
  if (!t) { t = document.createElement("div"); t.className = "toast"; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add("show");
  clearTimeout(toast._h); toast._h = setTimeout(() => t.classList.remove("show"), 1800);
}

async function buildProject() {
  const name = $("proj-name").value.trim() || "demo";
  const body = {
    name,
    script: $("script").value,
    backend: $("backend").value,
    model: $("model").value,
  };
  toast("生成中…（首次会调 LLM，可能要一会儿）");
  const res = await fetch("/api/projects", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  if (!res.ok) { toast("失败：" + res.status); return; }
  const out = await res.json();
  toast(`生成完成：${out.pages} 页`);
  await renderPages(name, out.pages);
}

async function loadProject() {
  const name = $("proj-name").value.trim() || "demo";
  const res = await fetch(`/api/projects/${encodeURIComponent(name)}`);
  if (!res.ok) { toast("项目不存在"); return; }
  const proj = await res.json();
  $("script").value = proj.script.raw_fountain || "";
  await renderPages(name, proj.pages.length);
}

async function renderPages(name, count) {
  const container = $("pages");
  container.innerHTML = "";
  $("page-count").textContent = `(共 ${count} 页)`;
  for (let i = 0; i < count; i++) {
    const card = document.createElement("div");
    card.className = "page-card";
    card.innerHTML = `<header><strong>页 ${i+1}</strong><span class="meta"><button data-relayout="${i}">重排</button></span></header><div class="svg-host">加载中…</div>`;
    container.appendChild(card);
    const svgRes = await fetch(`/api/projects/${encodeURIComponent(name)}/pages/${i}.svg`);
    if (svgRes.ok) {
      card.querySelector(".svg-host").innerHTML = await svgRes.text();
    } else {
      card.querySelector(".svg-host").textContent = "渲染失败";
    }
  }
}

document.addEventListener("click", async (e) => {
  if (e.target.id === "btn-build") buildProject();
  else if (e.target.id === "btn-load") loadProject();
  else if (e.target.dataset.export) {
    const kind = e.target.dataset.export;
    const name = $("proj-name").value.trim() || "demo";
    toast(`导出 ${kind.toUpperCase()}…`);
    const res = await fetch(`/api/projects/${encodeURIComponent(name)}/export/${kind}`, {method: "POST"});
    if (kind === "pdf" || kind === "cbz") {
      if (!res.ok) { toast("导出失败"); return; }
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${name}.${kind}`;
      a.click();
    } else {
      if (!res.ok) { toast("导出失败"); return; }
      const data = await res.json();
      toast(`已写入 ${data.files.length} 个文件`);
    }
  } else if (e.target.dataset.relayout !== undefined) {
    const idx = e.target.dataset.relayout;
    const name = $("proj-name").value.trim() || "demo";
    toast(`重排第 ${parseInt(idx)+1} 页…`);
    const res = await fetch(`/api/projects/${encodeURIComponent(name)}/relayout/${idx}`, {method: "POST"});
    if (!res.ok) { toast("失败"); return; }
    const svgRes = await fetch(`/api/projects/${encodeURIComponent(name)}/pages/${idx}.svg`);
    if (svgRes.ok) {
      const card = e.target.closest(".page-card");
      card.querySelector(".svg-host").innerHTML = await svgRes.text();
    }
  }
});
