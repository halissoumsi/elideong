document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }

  // Restore scroll position seamlessly after switching language
  try {
    const savedScroll = sessionStorage.getItem('elide_lang_scroll');
    if (savedScroll !== null) {
      sessionStorage.removeItem('elide_lang_scroll');
      const y = parseInt(savedScroll, 10);
      if (!Number.isNaN(y) && y > 0) {
        window.scrollTo({ top: y, behavior: 'instant' });
      }
    }
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        if (!btn.classList.contains('active')) {
          sessionStorage.setItem('elide_lang_scroll', String(window.scrollY));
        }
      });
    });
  } catch (e) {}

  // Header scroll dynamic visual change
  const header = document.querySelector('header');
  if (header) {
    const handleScroll = () => {
      if (window.scrollY > 50) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
  }

  // Burger Menu toggle
  const burger = document.getElementById('burger-menu');
  const nav = document.getElementById('nav-menu');

  if (burger && nav) {
    burger.addEventListener('click', () => {
      burger.classList.toggle('open');
      nav.classList.toggle('open');
    });

    // Close menu when clicking nav link
    const navLinks = nav.querySelectorAll('a');
    navLinks.forEach(link => {
      link.addEventListener('click', () => {
        burger.classList.remove('open');
        nav.classList.remove('open');
      });
    });
  }

  // Active state for navigation menu links on scroll (Desktop & Mobile Bottom App Bar)
  const sections = document.querySelectorAll('section[id]');
  const navA = document.querySelectorAll('header nav ul li a');
  const mobileNavItems = document.querySelectorAll('.mobile-bottom-nav .mobile-nav-item[data-section]');

  const setActiveNav = (sectionId) => {
    if (!sectionId) return;

    navA.forEach(a => {
      a.classList.toggle('active', a.getAttribute('href') === `#${sectionId}`);
    });

    if (mobileNavItems.length > 0) {
      const mobileTarget = sectionId === 'missions' ? 'apropos' : sectionId;
      mobileNavItems.forEach(item => {
        item.classList.toggle('active', item.getAttribute('data-section') === mobileTarget);
      });
    }
  };

  if (sections.length > 0) {
    window.addEventListener('scroll', () => {
      let current = sections[0].getAttribute('id');
      sections.forEach(section => {
        const sectionTop = section.offsetTop;
        if (window.scrollY >= (sectionTop - 160)) {
          current = section.getAttribute('id');
        }
      });
      setActiveNav(current);
    }, { passive: true });
  }

  mobileNavItems.forEach(item => {
    item.addEventListener('click', () => {
      setActiveNav(item.getAttribute('data-section'));
    });
  });

  // Register Service Worker for Mobile App (PWA) & Install Prompt (Android + iOS)
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {});
    });
  }

  const isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

  let deferredPrompt = null;
  const installBtn = document.getElementById('pwa-install-btn');
  const iosModal = document.getElementById('pwa-ios-modal');
  const iosCloseBtn = document.getElementById('pwa-ios-close');

  if (!isStandalone && installBtn) {
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      installBtn.style.display = 'inline-flex';
    });

    window.addEventListener('appinstalled', () => {
      deferredPrompt = null;
      installBtn.style.display = 'none';
    });

    // Sur iPhone/iPad Safari (hors mode installé), proposer le guide d'installation
    if (isIOS && isSafari && iosModal) {
      installBtn.style.display = 'inline-flex';
    }

    installBtn.addEventListener('click', async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const choice = await deferredPrompt.userChoice;
        deferredPrompt = null;
        if (choice && choice.outcome === 'accepted') {
          installBtn.style.display = 'none';
        }
      } else if (isIOS && iosModal) {
        iosModal.classList.add('open');
      }
    });
  }

  if (iosModal) {
    const closeIosModal = () => iosModal.classList.remove('open');
    if (iosCloseBtn) iosCloseBtn.addEventListener('click', closeIosModal);
    iosModal.addEventListener('click', (e) => {
      if (e.target === iosModal) closeIosModal();
    });
  }

  // Reveal elements on scroll using Intersection Observer
  const revealElements = document.querySelectorAll('.reveal');
  if (revealElements.length > 0 && 'IntersectionObserver' in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('active');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.05,
      rootMargin: '0px 0px -20px 0px'
    });

    revealElements.forEach(el => revealObserver.observe(el));
  } else {
    revealElements.forEach(el => el.classList.add('active'));
  }

  // Contact Form Handling (with real Flask API request)
  const contactForm = document.getElementById('contact-form');
  const formStatus = document.getElementById('form-status');

  if (contactForm && formStatus) {
    contactForm.addEventListener('submit', (e) => {
      e.preventDefault();
      
      const submitBtn = contactForm.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;
      const sendingLabel = contactForm.dataset.sending || 'Envoi en cours...';
      const defaultSuccessMsg = contactForm.dataset.success || 'Merci ! Votre message a bien été envoyé. Notre équipe vous répondra dans les plus brefs délais.';
      const defaultErrorMsg = contactForm.dataset.error || "Une erreur est survenue lors de l'envoi.";
      const networkErrorMsg = contactForm.dataset.networkError || 'Erreur de connexion. Impossible de joindre le serveur.';
      
      // Visual feedback loading state
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>${sendingLabel}</span>`;
      
      // Collect form data (including invisible anti-spam fields)
      const name = document.getElementById('form-name').value;
      const email = document.getElementById('form-email').value;
      const subject = document.getElementById('form-subject').value;
      const message = document.getElementById('form-message').value;
      const websiteEl = document.getElementById('contact-website');
      const tokenEl = document.getElementById('contact-token');
      const website_url = websiteEl ? websiteEl.value : '';
      const contact_token = tokenEl ? tokenEl.value : '';

      // Real fetch submission to Flask API
      fetch('/api/contact', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name, email, subject, message, website_url, contact_token })
      })
      .then(response => response.json().then(data => ({ status: response.status, body: data })))
      .then(res => {
        if (res.status === 200) {
          formStatus.className = "form-status success";
          formStatus.textContent = res.body.message || defaultSuccessMsg;
          contactForm.reset();
          if (tokenEl && res.body.next_token) {
            tokenEl.value = res.body.next_token;
          }
        } else {
          // Error state from server
          formStatus.className = "form-status error";
          formStatus.textContent = res.body.message || defaultErrorMsg;
        }
      })
      .catch(error => {
        console.error('Error submitting form:', error);
        formStatus.className = "form-status error";
        formStatus.textContent = networkErrorMsg;
      })
      .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      });
    });
  }

  // Partnership Form: activate invisible security token on human interaction (CSP-compliant, no inline JS)
  const partnerForm = document.getElementById('partner-form');
  const partnerTokenInput = document.getElementById('security_token');
  if (partnerForm && partnerTokenInput && partnerForm.dataset.securityToken) {
    const activatePartnerToken = () => {
      if (!partnerTokenInput.value) {
        partnerTokenInput.value = partnerForm.dataset.securityToken;
      }
    };
    partnerForm.addEventListener('focusin', activatePartnerToken);
    partnerForm.addEventListener('pointerdown', activatePartnerToken);
    partnerForm.addEventListener('keydown', activatePartnerToken);
  }

  // Donation Form (FedaPay): quick amount preset buttons (CSP-compliant)
  const amountInput = document.getElementById('donate-amount');
  const presetBtns = document.querySelectorAll('.amount-preset-btn');
  if (amountInput && presetBtns.length > 0) {
    presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const val = btn.dataset.amount;
        if (val) {
          amountInput.value = val;
          presetBtns.forEach(b => b.classList.toggle('active', b === btn));
        }
      });
    });

    amountInput.addEventListener('input', () => {
      const current = amountInput.value.trim();
      presetBtns.forEach(b => b.classList.toggle('active', b.dataset.amount === current));
    });
  }

  // FedaPay Checkout.js Popup Modal (Sobre : seul le montant est saisi, FedaPay gère le reste)
  const donateForm = document.getElementById('donate-form');
  if (donateForm && donateForm.dataset.fedapayPk && typeof FedaPay !== 'undefined') {
    donateForm.addEventListener('submit', (e) => {
      if (!donateForm.checkValidity()) return;
      e.preventDefault();

      const pk = donateForm.dataset.fedapayPk;
      const env = donateForm.dataset.fedapayEnv || 'sandbox';
      const returnUrl = donateForm.dataset.returnUrl || '/soutenir/retour';
      const amountVal = parseInt(document.getElementById('donate-amount').value, 10) || 0;
      if (amountVal < 500) return;

      const isEn = document.documentElement.lang === 'en';
      const description = isEn
        ? 'Donation — Les Élites de Demain NGO (ELiDe)'
        : "Don — ONG Les Élites de Demain (ELiDe)";

      try {
        const widget = FedaPay.init({
          public_key: pk,
          environment: env,
          locale: isEn ? 'en' : 'fr',
          transaction: {
            amount: amountVal,
            description
          },
          currency: { iso: 'XOF' },
          onComplete: (resp) => {
            if (resp && resp.reason === FedaPay.CHECKOUT_COMPLETED && resp.transaction) {
              const tx = resp.transaction;
              const params = new URLSearchParams({
                id: String(tx.id || ''),
                status: String(tx.status || 'approved'),
                ref: String(tx.reference || tx.id || ''),
                amount: String(tx.amount || amountVal)
              });
              window.location.href = `${returnUrl}?${params.toString()}`;
            }
          }
        });
        widget.open();
      } catch (err) {
        console.error('FedaPay modal error, falling back to server checkout:', err);
        donateForm.submit();
      }
    });
  }
});
