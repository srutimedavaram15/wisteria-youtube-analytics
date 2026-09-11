document.querySelectorAll('.tab').forEach(function (tab) {
  tab.addEventListener('click', function () {
    document.querySelectorAll('.tab').forEach(function (t) {
      t.classList.remove('active');
    });
    document.querySelectorAll('.section').forEach(function (s) {
      s.classList.remove('active');
    });

    tab.classList.add('active');
    var target = document.getElementById(tab.dataset.target);
    if (target) target.classList.add('active');
  });
});
