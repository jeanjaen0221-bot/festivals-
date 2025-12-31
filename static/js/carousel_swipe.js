// --- Swipe tactile pour le carousel des objets trouvés (accueil) ---
$(function() {
  var startX = null;
  var threshold = 40; // px minimum pour valider le swipe
  var $carousel = $('#foundCarousel');
  if ($carousel.length) {
    $carousel.on('touchstart', function(e) {
      var touch = e.originalEvent.touches[0];
      startX = touch.clientX;
    });
    $carousel.on('touchend', function(e) {
      if (startX === null) return;
      var touch = e.originalEvent.changedTouches[0];
      var deltaX = touch.clientX - startX;
      if (Math.abs(deltaX) > threshold) {
        if (deltaX < 0) {
          $carousel.carousel('next');
        } else {
          $carousel.carousel('prev');
        }
      }
      startX = null;
    });
  }
});
