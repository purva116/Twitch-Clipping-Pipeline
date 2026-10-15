let moments = [];
let filter = "all";
const LABELS = {
  clipped: [["good", "👍 good"], ["bad", "👎 bad"]],
  skipped: [["missed", "should've clipped"], ["correct_skip", "right to skip"]],
};

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  Object.assign(e, attrs);
  if (text !== undefined) e.textContent = text;
  return e;
}

async function saveLabel(m, value) {
  await fetch("/api/label", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: m.key, label: value }),
  });
  m.label = value;
  render();
}

function card(m) {
  const c = el("div", { className: "card" });
  c.append(el("div", { className: "meta" }, `#${m.channel} · ${new Date(m.ts).toLocaleString()}`));
  const tags = el("div");
  tags.append(el("span", { className: "badge " + m.action }, m.action));
  tags.append(el("span", { className: "badge" }, m.trigger || "spike"));
  if (m.mood && m.mood !== "none") tags.append(el("span", { className: "badge" }, m.mood));
  c.append(tags);
  const why = m.skip_reason
    ? `skipped: ${m.skip_reason}`
    : `${m.recent} msgs vs ~${m.normal} normal · reacting ${Math.round((m.reaction_ratio || 0) * 100)}%`;
  c.append(el("div", { className: "meta" }, why));
  c.append(el("div", {}, `top message: "${m.top_message}" x${m.top_count}`));
  if (m.video) {
    c.append(el("video", { src: m.video, controls: true, playsInline: true, preload: "metadata" }));
  } else if (m.url) {
    c.append(el("div", { className: "empty" }, "downloading clip... refresh in a minute"));
  } else {
    c.append(el("div", { className: "empty" }, "no clip (skipped moment)"));
  }
  if (m.sample && m.sample.length) {
    const d = el("details");
    d.append(el("summary", {}, "what chat was saying"));
    const ul = el("ul");
    m.sample.forEach(t => ul.append(el("li", {}, t)));
    d.append(ul);
    c.append(d);
  }
  const labelRow = el("div", { className: "row" });
  (LABELS[m.action] || LABELS.clipped).forEach(([value, text]) => {
    const b = el("button", { className: m.label === value ? "picked" : "" }, text);
    b.onclick = () => saveLabel(m, value);
    labelRow.append(b);
  });
  c.append(labelRow);
  if (m.video) {
    const saveRow = el("div", { className: "row" });
    saveRow.append(el("a", { href: m.video, download: `${m.channel}-${m.clip_id}.mp4` }, "⬇ save video"));
    if (m.url) saveRow.append(el("a", { href: m.url, target: "_blank" }, "open on twitch"));
    c.append(saveRow);
  }
  return c;
}

function render() {
  const list = document.getElementById("list");
  list.replaceChildren();
  const shown = moments.filter(m =>
    filter === "all" || (filter === "unlabeled" ? !m.label : m.action === filter));
  shown.forEach(m => list.append(card(m)));
  if (!shown.length) list.append(el("div", { className: "empty" }, "nothing here yet"));
  const labeled = moments.filter(m => m.label).length;
  document.getElementById("count").textContent = `${labeled}/${moments.length} labeled`;
}

document.querySelectorAll(".filters button").forEach(b => {
  b.onclick = () => {
    document.querySelectorAll(".filters button").forEach(x => x.classList.remove("on"));
    b.classList.add("on");
    filter = b.dataset.f;
    render();
  };
});

fetch("/api/moments").then(r => r.json()).then(data => { moments = data; render(); });