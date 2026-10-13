const $ = (id) => document.getElementById(id);
const foodEmoji = {"Prepared meals":"🍱","Produce":"🥦","Bakery":"🥖","Dairy":"🥛","Packaged food":"🥫"};
let smartOn = false;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function timeLeft(minutes) {
  if (minutes <= 0) return "Pickup deadline passed";
  if (minutes < 60) return `${minutes} min left`;
  const h = Math.floor(minutes/60), m = minutes%60;
  if (h < 24) return `${h}h ${m}m left`;
  return `${Math.floor(h/24)}d ${h%24}h left`;
}
function showToast(message) {
  const t = $("toast"); t.textContent = message; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 3200);
}
function toggleSmart() {
  smartOn = !smartOn;
  $("smart-panel").classList.toggle("show", smartOn);
  $("smart-state").textContent = smartOn ? "On" : "Off";
  document.querySelector(".filter-button").classList.toggle("active", smartOn);
  loadListings();
}
async function loadStats() {
  try {
    const s = await (await fetch("/api/stats")).json();
    $("stat-listings").textContent = s.listings;
    $("stat-available").textContent = s.available;
    $("stat-reserved").textContent = s.reservations;
    $("stat-quantity").textContent = s.reserved_quantity;
  } catch(e) { console.error(e); }
}
async function loadListings() {
  const params = new URLSearchParams();
  if ($("search").value.trim()) params.set("search", $("search").value.trim());
  if ($("category").value) params.set("category", $("category").value);
  if ($("mode").value) params.set("mode", $("mode").value);
  if (smartOn) {
    if ($("lat").value !== "") params.set("lat", $("lat").value);
    if ($("lon").value !== "") params.set("lon", $("lon").value);
    if ($("needed").value !== "") params.set("needed", $("needed").value);
  }
  try {
    const response = await fetch("/api/listings?" + params.toString());
    const items = await response.json();
    renderListings(items);
  } catch(e) {
    $("listing-grid").innerHTML = '<div class="loading">Could not load listings. Is the Flask server running?</div>';
  }
}
function renderListings(items) {
  const grid = $("listing-grid");
  const urgent = items.some(x => x.urgency === "Urgent" || x.urgency === "Soon");
  $("alert-banner").classList.toggle("hidden", !urgent);
  $("empty-state").classList.toggle("hidden", items.length !== 0);
  if (!items.length) { grid.innerHTML = ""; return; }
  grid.innerHTML = items.map(x => {
    const emoji = foodEmoji[x.category] || "🍽️";
    const badgeClass = x.urgency === "Urgent" ? "urgent" : x.urgency === "Soon" ? "soon" : "";
    const modeBadge = x.mode === "Discounted" ? "discount" : "";
    const price = x.mode === "Donation" ? "FREE" : `₹${Number(x.price).toFixed(0)}/${escapeHtml(x.unit)}`;
    let distance = x.distance_km == null ? "" : `📍 ${x.distance_km.toFixed(1)} km away`;
    const match = smartOn ? `<div class="match-note">✧ Smart match score: ${x.match_score}/100 · ranked by urgency, distance and quantity</div>` : "";
    return `<article class="food-card">
      <div class="food-visual ${x.category.toLowerCase().replaceAll(" ","-")}"><span class="badge ${badgeClass}">${escapeHtml(x.urgency === "Available" ? "AVAILABLE" : x.urgency.toUpperCase())}</span><span>${emoji}</span></div>
      <div class="food-content"><div class="food-title-row"><h3>${escapeHtml(x.title)}</h3><span class="price">${price}</span></div>
      <p class="food-provider">Provided by ${escapeHtml(x.provider)}</p>
      <div class="food-meta"><span>▦ ${x.quantity} ${escapeHtml(x.unit)} listed</span><span class="badge ${modeBadge}">${escapeHtml(x.mode)}</span></div>
      <p class="food-location">⌖ ${escapeHtml(x.location)} ${distance ? " · "+distance : ""}</p>
      <div class="deadline"><span>⏱ Pickup deadline</span><b>${timeLeft(x.minutes_left)}</b></div>
      ${match}<button class="reserve-button" onclick="reserveFood(${x.id},${x.quantity},'${escapeHtml(x.unit).replaceAll("'","\\'")}')">Reserve food →</button>
      </div></article>`;
  }).join("");
}
async function reserveFood(id, max, unit) {
  const recipient = prompt("Enter your name or organization:");
  if (!recipient || !recipient.trim()) return;
  const q = prompt(`How many ${unit} would you like to reserve? (Available: ${max})`, "1");
  if (q === null) return;
  try {
    const response = await fetch(`/api/listings/${id}/reserve`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({recipient:recipient.trim(),quantity:Number(q)})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Reservation failed.");
    showToast(result.message); await Promise.all([loadListings(),loadStats()]);
  } catch(e) { showToast(e.message); }
}
function openForm() {
  $("listing-modal").classList.remove("hidden");
  $("form-error").classList.add("hidden");
  const d = new Date(Date.now()+3*60*60*1000);
  d.setMinutes(d.getMinutes()-d.getTimezoneOffset());
  $("listing-form").elements.pickup_by.min = new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16);
  if (!$("listing-form").elements.pickup_by.value) $("listing-form").elements.pickup_by.value = d.toISOString().slice(0,16);
}
function closeForm() { $("listing-modal").classList.add("hidden"); }
$("offer-mode").addEventListener("change", e => {
  const price = $("listing-form").elements.price;
  if (e.target.value === "Donation") price.value = "0";
});
$("listing-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  ["quantity","price","lat","lon"].forEach(k => {
    if (data[k] === "") data[k] = null;
    else if (data[k] !== undefined && data[k] !== null) data[k] = Number(data[k]);
  });
  if (data.mode === "Donation") data.price = 0;
  $("form-error").classList.add("hidden");
  try {
    const response = await fetch("/api/listings", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not create listing.");
    closeForm(); form.reset(); showToast(result.message);
    await Promise.all([loadListings(),loadStats()]);
    document.querySelector("#discover").scrollIntoView({behavior:"smooth"});
  } catch(err) {
    $("form-error").textContent = err.message;
    $("form-error").classList.remove("hidden");
  }
});
document.addEventListener("keydown", e => { if (e.key === "Escape") closeForm(); });
loadListings(); loadStats();
