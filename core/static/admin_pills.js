document.addEventListener('DOMContentLoaded', function () {
  // cibler les deux groupes (Member.qualifications et Session.required_quals)
  ['#id_qualifications', '#id_required_quals'].forEach(function (sel) {
    var root = document.querySelector(sel);
    if (!root) return;
    root.querySelectorAll('input[type="checkbox"]').forEach(function (cb) {
      var wrapper = cb.closest('div'); // chaque option est dans un <div>
      if (!wrapper) return;
      function sync() { wrapper.classList.toggle('is-checked', cb.checked); }
      sync();
      cb.addEventListener('change', sync);
    });
  });
});
