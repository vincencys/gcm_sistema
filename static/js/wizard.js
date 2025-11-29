// CSRF helper (Django)
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

window.Wizard = {
  toggle(sel) {
    const el = document.querySelector(sel);
    if (!el) return;
    el.classList.toggle('hidden');
    if (!el.classList.contains('hidden')) el.scrollIntoView({behavior:'smooth', block:'center'});
  }
};

// Tabs
document.addEventListener("click", function(e){
  const a = e.target.closest(".tabs .tab");
  if (!a) return;
  e.preventDefault();
  document.querySelectorAll(".tabs .tab").forEach(t => t.classList.remove("active"));
  a.classList.add("active");
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  const panel = document.querySelector(a.getAttribute("href"));
  if (panel) panel.classList.add("active");
});

// AJAX submit for checklist
document.addEventListener("submit", async function(e){
  const form = e.target;
  if (form.id !== "form-checklist") return;
  e.preventDefault();
  const url = form.action;
  const formData = new FormData(form);
  const res = await fetch(url, {
    method: "POST",
    headers: {"X-CSRFToken": getCookie("csrftoken"), "X-Requested-With": "XMLHttpRequest"},
    body: formData
  });
  if (res.ok) {
    alert("Checklist salvo!");
  } else {
    alert("Erro ao salvar checklist.");
  }
});

// Progressive enhance: submit abastecimento via fetch e atualizar tabela
document.addEventListener("submit", async function(e){
  const form = e.target;
  if (form.id !== "form-abastecimento") return;
  // deixa o comportamento normal se FormData tiver arquivo muito grande ou browser antigo
  if (!window.fetch) return;
  e.preventDefault();

  const url = form.action;
  const fd = new FormData(form);
  const res = await fetch(url, {
    method: "POST",
    headers: {"X-CSRFToken": getCookie("csrftoken"), "X-Requested-With": "XMLHttpRequest"},
    body: fd
  });
  if (res.ok) {
    const data = await res.json();
    if (data.html) {
      document.getElementById("tbody-abastecimentos").innerHTML = data.html;
      form.reset();
      Wizard.toggle("#form-abastecimento");
      alert("Abastecimento salvo!");
    }
  } else {
    const err = await res.json().catch(()=>({}));
    alert("Erro ao salvar: " + (err.errors ? JSON.stringify(err.errors) : res.status));
  }
});

// Template filter helper: get_item in dict
// (When using Django, add this to your template builtins; here we emulate with JS no-op)
