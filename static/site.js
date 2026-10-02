'use strict';

/* Progressive enhancement only: every data operation remains a Django POST. */
(() => {
  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const message = form.getAttribute('data-confirm');
      if (message && !window.confirm(message)) {
        event.preventDefault();
      }
    });
  });

  const toggle = document.querySelector('.nav-toggle');
  const navigation = document.getElementById('site-navigation');
  if (!toggle || !navigation) return;

  const mobile = window.matchMedia('(max-width: 740px)');
  document.documentElement.classList.add('nav-enhanced');

  const setExpanded = (expanded) => {
    navigation.classList.toggle('is-open', expanded);
    toggle.setAttribute('aria-expanded', String(expanded));
    toggle.textContent = expanded ? '收起导航' : '展开导航';
  };

  const syncViewport = () => {
    toggle.hidden = !mobile.matches;
    setExpanded(false);
  };

  toggle.addEventListener('click', () => {
    setExpanded(toggle.getAttribute('aria-expanded') !== 'true');
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && mobile.matches && navigation.classList.contains('is-open')) {
      setExpanded(false);
      toggle.focus();
    }
  });

  document.addEventListener('click', (event) => {
    if (mobile.matches && navigation.classList.contains('is-open') &&
        !navigation.contains(event.target) && !toggle.contains(event.target)) {
      const focusWasInside = navigation.contains(document.activeElement);
      setExpanded(false);
      if (focusWasInside) toggle.focus();
    }
  });

  navigation.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      if (mobile.matches) setExpanded(false);
    });
  });

  if (typeof mobile.addEventListener === 'function') {
    mobile.addEventListener('change', syncViewport);
  } else {
    mobile.addListener(syncViewport);
  }
  syncViewport();
})();
