const menuButton = document.querySelector('.menu-btn');
const nav = document.querySelector('.nav');
menuButton.addEventListener('click', () => {
  const open = nav.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
});
document.querySelectorAll('.nav-links a').forEach(link => link.addEventListener('click', () => nav.classList.remove('open')));

const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
}, { threshold: .12 });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

const arabicDigits = new Intl.NumberFormat('ar-JO');
let counted = false;
const statsObserver = new IntersectionObserver(([entry]) => {
  if (!entry.isIntersecting || counted) return;
  counted = true;
  document.querySelectorAll('[data-count]').forEach(el => {
    const target = Number(el.dataset.count); let value = 0;
    const step = Math.max(1, Math.round(target / 45));
    const timer = setInterval(() => {
      value = Math.min(target, value + step); el.textContent = arabicDigits.format(value) + (target === 2500 ? '+' : '+');
      if (value === target) clearInterval(timer);
    }, 28);
  });
}, { threshold: .5 });
statsObserver.observe(document.querySelector('.hero-stats'));

document.querySelectorAll('.filters button').forEach(button => button.addEventListener('click', () => {
  document.querySelector('.filters .active').classList.remove('active'); button.classList.add('active');
  const filter = button.dataset.filter;
  document.querySelectorAll('.plant-card').forEach(card => card.classList.toggle('hidden', filter !== 'all' && !card.dataset.region.includes(filter)));
}));
document.querySelectorAll('.heart').forEach(button => button.addEventListener('click', () => {
  button.classList.toggle('saved'); button.textContent = button.classList.contains('saved') ? '♥' : '♡';
}));
document.querySelectorAll('.region-list button').forEach(button => button.addEventListener('click', () => {
  document.querySelector('.region-list .active').classList.remove('active'); button.classList.add('active');
}));
document.querySelector('.newsletter form').addEventListener('submit', event => {
  event.preventDefault(); event.currentTarget.reset(); document.querySelector('.form-note').textContent = 'شكرًا! ستصلك الحكاية القادمة.';
});
document.querySelector('.share-btn').addEventListener('click', async () => {
  if (navigator.share) await navigator.share({ title: 'نَبْت', text: 'اكتشف نباتات الأردن البرية', url: location.href });
  else { await navigator.clipboard.writeText(location.href); document.querySelector('.share-btn').textContent = 'تم نسخ الرابط ✓'; }
});
