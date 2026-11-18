document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide Icons
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }

  // Header scroll dynamic visual change
  const header = document.querySelector('header');
  const handleScroll = () => {
    if (window.scrollY > 50) {
      header.classList.add('scrolled');
    } else {
      header.classList.remove('scrolled');
    }
  };
  window.addEventListener('scroll', handleScroll);
  handleScroll(); // Initial check

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
  const sections = document.querySelectorAll('section, footer');
  const navA = document.querySelectorAll('nav ul li a');
  const mobileNavItems = document.querySelectorAll('.mobile-bottom-nav .mobile-nav-item[data-section]');

  window.addEventListener('scroll', () => {
    let current = '';
    sections.forEach(section => {
      const sectionTop = section.offsetTop;
      if (window.scrollY >= (sectionTop - 180)) {
        current = section.getAttribute('id');
      }
    });

    navA.forEach(a => {
      a.classList.remove('active');
      if (a.getAttribute('href') === `#${current}`) {
        a.classList.add('active');
      }
    });

    if (current && mobileNavItems.length > 0) {
      mobileNavItems.forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-section') === current) {
          item.classList.add('active');
        }
      });
    }
  });

  // Register Service Worker for Mobile App (PWA) & Install Prompt
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }

  let deferredPrompt;
  const installBtn = document.getElementById('pwa-install-btn');
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (installBtn) {
      installBtn.style.display = 'inline-flex';
    }
  });

  if (installBtn) {
    installBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      installBtn.style.display = 'none';
    });
  }

  // Reveal elements on scroll using Intersection Observer
  const revealElements = document.querySelectorAll('.reveal');
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('active');
        // Stop observing once revealed to retain visual state
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.15,
    rootMargin: '0px 0px -50px 0px'
  });

  revealElements.forEach(el => revealObserver.observe(el));

  // Contact Form Handling (with real Flask API request)
  const contactForm = document.getElementById('contact-form');
  const formStatus = document.getElementById('form-status');

  if (contactForm && formStatus) {
    contactForm.addEventListener('submit', (e) => {
      e.preventDefault();
      
      const submitBtn = contactForm.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;
      
      // Visual feedback loading state
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Envoi en cours...</span>`;
      
      // Collect form data
      const name = document.getElementById('form-name').value;
      const email = document.getElementById('form-email').value;
      const subject = document.getElementById('form-subject').value;
      const message = document.getElementById('form-message').value;

      // Real fetch submission to Flask API
      fetch('/api/contact', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name, email, subject, message })
      })
      .then(response => response.json().then(data => ({ status: response.status, body: data })))
      .then(res => {
        if (res.status === 200) {
          // Success state with direct WhatsApp and Email options
          formStatus.className = "form-status success";
          formStatus.innerHTML = `
            <p style="margin-bottom: 12px; color: #2a9d8f;">Merci pour votre message ! Vous pouvez également l'envoyer directement en un clic :</p>
            <div style="display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;">
              <a href="${res.body.whatsapp_url}" target="_blank" class="btn btn-primary" style="background: #25D366; padding: 10px 18px; font-size: 0.85rem;">
                Envoyer sur WhatsApp
              </a>
              <a href="${res.body.mailto_url}" class="btn btn-secondary" style="padding: 8px 16px; font-size: 0.85rem;">
                Ouvrir dans mon application Email
              </a>
            </div>
          `;
          contactForm.reset();
        } else {
          // Error state from server
          formStatus.className = "form-status error";
          formStatus.textContent = res.body.message || "Une erreur est survenue lors de l'envoi.";
        }
      })
      .catch(error => {
        console.error('Error submitting form:', error);
        formStatus.className = "form-status error";
        formStatus.textContent = "Erreur de connexion. Impossible de joindre le serveur.";
      })
      .finally(() => {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
      });
    });
  }
});
