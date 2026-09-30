(() => {
  const body = document.body;
  const menuTriggers = [...document.querySelectorAll('[data-menu-trigger]')];
  const menus = [...document.querySelectorAll('[data-menu]')];
  let closeTimer;

  const closeMenus = () => {
    window.clearTimeout(closeTimer);
    menuTriggers.forEach((trigger) => trigger.setAttribute('aria-expanded', 'false'));
    menus.forEach((menu) => {
      menu.classList.remove('is-open');
      menu.setAttribute('aria-hidden', 'true');
    });
  };

  const openMenu = (name) => {
    window.clearTimeout(closeTimer);
    menuTriggers.forEach((trigger) => trigger.setAttribute('aria-expanded', String(trigger.dataset.menuTrigger === name)));
    menus.forEach((menu) => {
      const isCurrent = menu.dataset.menu === name;
      menu.classList.toggle('is-open', isCurrent);
      menu.setAttribute('aria-hidden', String(!isCurrent));
    });
  };

  menuTriggers.forEach((trigger) => {
    trigger.addEventListener('click', () => {
      trigger.getAttribute('aria-expanded') === 'true' ? closeMenus() : openMenu(trigger.dataset.menuTrigger);
    });
    trigger.closest('.nav-group').addEventListener('mouseenter', () => openMenu(trigger.dataset.menuTrigger));
  });

  document.querySelector('[data-header]').addEventListener('mouseleave', () => {
    closeTimer = window.setTimeout(closeMenus, 140);
  });
  menus.forEach((menu) => menu.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMenus)));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeMenus();
  });

  const mobileToggle = document.querySelector('[data-mobile-toggle]');
  const mobilePanel = document.querySelector('[data-mobile-panel]');
  const closeMobile = () => {
    mobileToggle.setAttribute('aria-expanded', 'false');
    mobileToggle.setAttribute('aria-label', 'Open menu');
    mobilePanel.classList.remove('is-open');
    mobilePanel.setAttribute('aria-hidden', 'true');
    body.classList.remove('menu-open');
  };

  mobileToggle.addEventListener('click', () => {
    const opening = mobileToggle.getAttribute('aria-expanded') !== 'true';
    mobileToggle.setAttribute('aria-expanded', String(opening));
    mobileToggle.setAttribute('aria-label', opening ? 'Close menu' : 'Open menu');
    mobilePanel.classList.toggle('is-open', opening);
    mobilePanel.setAttribute('aria-hidden', String(!opening));
    body.classList.toggle('menu-open', opening);
  });
  mobilePanel.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeMobile));

  const customSelect = document.querySelector('[data-select]');
  const selectTrigger = customSelect.querySelector('[data-select-trigger]');
  const selectValue = customSelect.querySelector('[data-select-value]');
  const selectOptions = [...customSelect.querySelectorAll('[role="option"]')];
  const prompt = document.querySelector('[data-demo-prompt]');
  const output = document.querySelector('[data-demo-output]');
  const promptText = {
    Explore: 'Turn our scattered customer notes into three clear priorities for next quarter.',
    Create: 'Draft a thoughtful launch note that sounds confident, clear, and human.',
    Analyze: 'Compare these options and show the trade-offs that matter to our customers.',
    Build: 'Turn this product idea into a practical first version and a plan to improve it.'
  };

  const setSelectOpen = (open) => {
    customSelect.classList.toggle('is-open', open);
    selectTrigger.setAttribute('aria-expanded', String(open));
  };

  selectTrigger.addEventListener('click', () => setSelectOpen(!customSelect.classList.contains('is-open')));
  selectOptions.forEach((option) => {
    option.addEventListener('click', () => {
      selectOptions.forEach((item) => item.setAttribute('aria-selected', String(item === option)));
      selectValue.textContent = option.dataset.value;
      prompt.textContent = promptText[option.dataset.value];
      setSelectOpen(false);
    });
  });
  document.addEventListener('click', (event) => {
    if (!customSelect.contains(event.target)) setSelectOpen(false);
  });

  document.querySelector('[data-demo-send]').addEventListener('click', () => {
    output.classList.add('is-refreshing');
    window.setTimeout(() => output.classList.remove('is-refreshing'), 260);
  });

  const filterButtons = [...document.querySelectorAll('[data-filter]')];
  const productCards = [...document.querySelectorAll('[data-product]')];
  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      const filter = button.dataset.filter;
      filterButtons.forEach((item) => {
        const active = item === button;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-selected', String(active));
      });
      productCards.forEach((card) => {
        card.classList.toggle('is-hidden', filter !== 'all' && !card.dataset.product.split(' ').includes(filter));
      });
    });
  });

  const reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -30px' });
    reveals.forEach((element) => observer.observe(element));
  } else {
    reveals.forEach((element) => element.classList.add('is-visible'));
  }

  document.querySelector('[data-year]').textContent = new Date().getFullYear();
})();
