// scripts.js - Fichier JavaScript principal pour l'application MonCaisson

document.addEventListener('DOMContentLoaded', function() {
    // 1. Activation des tooltips Bootstrap
    initTooltips();
    
    // 2. Gestion des confirmations avant suppression/annulation
    setupFormConfirmations();
    
    // 3. Gestion des boutons de réservation
    setupReservationButtons();
    
    // 4. Gestion du défilement fluide et des ancres
    setupSmoothScrolling();
    
    // 5. Gestion des sections actives
    setupActiveSections();
});

/**
 * Initialise les tooltips Bootstrap
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            trigger: 'hover focus'
        });
    });
}

/**
 * Configure la confirmation avant soumission pour les formulaires critiques
 */
function setupFormConfirmations() {
    document.querySelectorAll('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', function(e) {
            const message = this.getAttribute('data-confirm') || 'Êtes-vous sûr de vouloir effectuer cette action ?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
}

/**
 * Gère le comportement des boutons de réservation
 */
function setupReservationButtons() {
    document.querySelectorAll('.btn-reserver').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.getAttribute('href') || this.dataset.reservationUrl;
            if (url && url.startsWith('/')) {
                window.location.href = url;
            } else {
                console.error('URL de réservation invalide:', url);
            }
        });
    });
}

/**
 * Configure le défilement fluide et la gestion des ancres
 */
function setupSmoothScrolling() {
    // Gestion de l'ancre au chargement
    if (window.location.hash) {
        scrollToAnchor(window.location.hash, 100);
    }

    // Gestion des clics sur liens d'ancrage
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            scrollToAnchor(targetId, 0);
            history.pushState(null, null, targetId);
        });
    });
}

/**
 * Scroll fluide vers une ancre avec délai
 */
function scrollToAnchor(anchorId, delay) {
    const target = document.querySelector(anchorId);
    if (target) {
        setTimeout(() => {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
            // Mise en évidence temporaire
            highlightSection(target);
        }, delay);
    }
}

/**
 * Mise en évidence d'une section
 */
function highlightSection(element) {
    element.classList.add('highlighted-section');
    setTimeout(() => {
        element.classList.remove('highlighted-section');
    }, 2000);
}

/**
 * Gestion des sections actives dans la sidebar
 */
function setupActiveSections() {
    const sections = document.querySelectorAll('[id^="mes-reservations"], [id^="favoris"]');
    const navLinks = document.querySelectorAll('#sidebar a[href^="#"]');
    
    if (sections.length === 0 || navLinks.length === 0) return;

    // Observer l'intersection des sections
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const id = '#' + entry.target.id;
            const navLink = document.querySelector(`#sidebar a[href="${id}"]`);
            if (navLink) {
                if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
                    navLink.classList.add('active');
                } else {
                    navLink.classList.remove('active');
                }
            }
        });
    }, {
        threshold: 0.5,
        rootMargin: '0px 0px -50% 0px'
    });

    sections.forEach(section => {
        observer.observe(section);
    });
}

// Gestion des événements HTMX (si utilisé)
document.body.addEventListener('htmx:afterSwap', function() {
    // Réinitialise les composants après un swap HTMX
    initTooltips();
    setupFormConfirmations();
    setupReservationButtons();
});

/**
 * Initialise le suivi de scroll et la barre de progression
 */
function initScrollTracking() {
  // Barre de progression du scroll
  const progressBar = document.createElement('div');
  progressBar.className = 'scroll-progress';
  document.body.appendChild(progressBar);
  
  // Indicateurs de section
  const sections = document.querySelectorAll('[id^="mes-reservations"], [id^="favoris"]');
  if (sections.length > 1) {
    const sectionIndicator = document.createElement('div');
    sectionIndicator.className = 'section-indicator d-none d-lg-flex';
    
    sections.forEach(section => {
      const link = document.createElement('a');
      link.href = `#${section.id}`;
      sectionIndicator.appendChild(link);
    });
    
    document.body.appendChild(sectionIndicator);
  }

  // Écouteurs d'événements
  window.addEventListener('scroll', updateScrollProgress);
  window.addEventListener('scroll', updateActiveSection);
}

/**
 * Met à jour la barre de progression du scroll
 */
function updateScrollProgress() {
  const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
  const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
  const scrolled = (winScroll / height) * 100;
  document.querySelector('.scroll-progress').style.width = scrolled + '%';
}

/**
 * Met à jour l'indicateur de section active
 */
function updateActiveSection() {
  const sections = document.querySelectorAll('[id^="mes-reservations"], [id^="favoris"]');
  const navLinks = document.querySelectorAll('.section-indicator a');
  
  let currentSection = '';
  sections.forEach(section => {
    const sectionTop = section.offsetTop - 100;
    if (window.scrollY >= sectionTop) {
      currentSection = `#${section.id}`;
    }
  });
  
  navLinks.forEach(link => {
    link.classList.remove('active');
    if (link.getAttribute('href') === currentSection) {
      link.classList.add('active');
    }
  });
}

// Initialiser le suivi de scroll au chargement
document.addEventListener('DOMContentLoaded', initScrollTracking);