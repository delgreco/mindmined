// support dark or light mode

detectDarkPref();

function detectDarkPref() {
    let auto_dark = window.localStorage.getItem('auto_dark');
    let user_dark = window.localStorage.getItem('user_dark');
    if ( user_dark == 'yes' ) {
        console.log('user dark');
        goDark();
    }
    else if ( user_dark == 'no' ) {
        goLight();
    }
    else { // if no manually set preference, we try to auto-detect
        if ( auto_dark ) {
            console.log('auto dark');
            goDark();
        }
        else { // see if there is an OS / browser preference
            if ( window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ) {
                window.localStorage.setItem('auto_dark', '1');
                goDark();
                console.log('setting auto_dark according to prefers-color-scheme');
            }
            else {
                console.log('no prefers-color-scheme: dark detected');
            }
        }
    }
}

function goDark() {
    if ( window.location.href.indexOf("preferences" ) > -1 ) { 
        document.getElementById("dark_mode").checked = true;
    }
    let body = document.querySelector('body');
    body.style.backgroundColor = "#000000";
    body.style.color = "#FFFFFF";
    //document.getElementById("gallery_head").classList.add('gallery_head_dark');
    let gallery_banner = document.getElementById("gallery_head");
    let gallery_mm = document.getElementById("gallery_mm_logo");
    if ( gallery_banner ) {
        gallery_banner.classList.add('gallery_head_dark');
        gallery_mm.classList.add('gallery_mm_dark');
    }
    let elements = document.querySelectorAll('.invertible');
    elements.forEach(element => {
        element.style.filter = 'invert(100%)';
    });
}

function goLight() {
    if ( window.location.href.indexOf("preferences" ) > -1 ) { 
        document.getElementById("dark_mode").checked = false;
    }
    let body = document.querySelector('body');
    body.style.backgroundColor = "#FFFFFF";
    body.style.color = "#000000";
    let gallery_banner = document.getElementById("gallery_head");
    let gallery_mm = document.getElementById("gallery_mm_logo");
    if ( gallery_banner ) {
        gallery_banner.classList.add('gallery_head_light');
        gallery_mm.classList.add('gallery_mm_light');
    }
    let elements = document.querySelectorAll('.invertible');
    elements.forEach(element => {
        element.style.filter = 'invert(100%)';
    });
}

