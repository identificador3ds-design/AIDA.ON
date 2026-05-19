document.addEventListener('DOMContentLoaded', () => {
    // 1. Header Scrolled Effect
    const header = document.querySelector('.cabecalho');
    window.addEventListener('scroll', () => {
        header.classList.toggle('scrolled', window.scrollY > 50);
    });

    // 2. Menu Mobile
    const toggle = document.querySelector('.menu-toggle');
    const nav = document.querySelector('.navbar');
    
    toggle.addEventListener('click', () => {
        toggle.classList.toggle('active');
        nav.classList.toggle('active');
    });

    // 3. Scroll Reveal (Animação de Entrada)
    const observerOptions = { threshold: 0.1 };
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);

    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
});