$(document).ready(function(){
	console.log("Initiating slider")
	$('.home-slider').slick({slidesToShow: 3,
		slidesToScroll: 3,
		autoplay: true,
		autoplaySpeed: 2000
	});
});

