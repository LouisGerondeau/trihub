(function () {
  // Lecture du JSON global injecté via {{ available_coaches|json_script:"coachesData" }}
  const COACHES = JSON.parse(document.getElementById('coachesData').textContent || '{}');

  const debounce = (fn, delay = 250) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), delay);
    };
  };

  const norm = s => (s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, ''); // retire les accents

  const boxes = document.querySelectorAll('.add-box');

  boxes.forEach(box => {
    if (box.dataset.bound === '1') return; // garde-fou anti double-bind
    box.dataset.bound = '1';

    const input = box.querySelector('.coach-input');
    const listWrap = box.querySelector('.suggest');
    const list = listWrap.querySelector('ul');
    const cat = box.dataset.category;
    const sid = box.dataset.session;

    const available = COACHES[sid] || []; // [{id, name}, ...]

    let lastHTML = '';

    const render = () => {
      const q = norm(input.value.trim());
      if (!q) {
        list.innerHTML = '';
        listWrap.classList.remove('show');
        lastHTML = '';
        return;
      }

      const results = available.filter(c => norm(c.name).includes(q)).slice(0, 20);
      const html = results.length
        ? results.map(c => `<li data-id="${c.id}">${c.name}</li>`).join('')
        : '<li style="pointer-events:none;">Aucun résultat</li>';

      if (html !== lastHTML) {
        list.innerHTML = html;
        listWrap.classList.add('show');
        lastHTML = html;
      }
    };

    const onInput = debounce(() => {
      if (document.activeElement !== input) return; // évite les événements parasites
      render();
    }, 250);

    input.addEventListener('input', onInput);

    list.addEventListener('click', e => {
      const li = e.target.closest('li');
      if (!li?.dataset.id) return;
      const coachId = li.dataset.id;
      window.location = `/public/${cat}/${sid}/assign/?coach_id=${coachId}`;
    });

    document.addEventListener('click', e => {
      if (!box.contains(e.target)) listWrap.classList.remove('show');
    });
  });
})();