(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll("#toc-nav a"));
  var sections = links
    .map(function (a) { return document.getElementById(a.getAttribute("data-target")); })
    .filter(Boolean);

  function setActive(id) {
    links.forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("data-target") === id);
    });
  }

  links.forEach(function (a) {
    a.addEventListener("click", function () {
      setActive(a.getAttribute("data-target"));
    });
  });

  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) setActive(entry.target.id);
        });
      },
      { rootMargin: "-35% 0px -55% 0px", threshold: 0 }
    );
    sections.forEach(function (s) { observer.observe(s); });
  }

  setActive("architecture");
})();
