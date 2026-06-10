"""biomech3d.py — a procedural, spinnable 3D biomechanics viewer.

Per the "3D rendering stack" brief, biomechanics primitives (bones, joints,
force vectors, moment arms) are best GENERATED IN CODE rather than sourced as
binary meshes: lighter, fully parametric, version-controlled, and zero license
overhead. This builds a third-class-lever model of the elbow entirely from
Three.js primitives (cylinder bones, a sphere joint, ArrowHelper force vectors)
and lets the learner drag to rotate it in 3D and sweep the joint angle.

Engine: Three.js r160, dynamic-imported from jsDelivr — the SAME module the
lift steppers already load, so this adds no new dependency. Rotation is a small
custom pointer-drag (core three.module.js has no OrbitControls).

Robustness: if WebGL is unavailable or the import fails, it reveals a static
SVG fallback so the daily page NEVER blanks (P0 rule). No localStorage / no FSRS
contact — purely ephemeral lesson scaffolding.
"""
from __future__ import annotations

import biomech  # reuse _shell, _uid, _predict_block, predict CSS/JS


def lever_3d() -> str:
    uid = biomech._uid("l3d")

    # Static SVG fallback (revealed only if WebGL/import fails).
    fallback = r'''
<svg viewBox="0 0 320 200" style="width:100%;max-height:200px" xmlns="http://www.w3.org/2000/svg">
  <line x1="60" y1="40" x2="60" y2="150" stroke="#9ba3b4" stroke-width="6" stroke-linecap="round"/>
  <line x1="60" y1="150" x2="240" y2="150" stroke="#67e8b0" stroke-width="6" stroke-linecap="round"/>
  <circle cx="60" cy="150" r="8" fill="#ffb86b"/>
  <line x1="240" y1="150" x2="240" y2="186" stroke="#ff7a7a" stroke-width="2.5"/>
  <path d="M240 188 l-5 -12 l10 0 z" fill="#ff7a7a"/>
  <line x1="90" y1="60" x2="78" y2="150" stroke="#5ec8ff" stroke-width="2.5"/>
  <text x="150" y="176" fill="#9ba3b4" font-size="10" text-anchor="middle">3D needs WebGL — showing the 2D lever instead</text>
</svg>'''

    stage = (
        '<div class="bm3d-stage" style="position:relative;width:100%;height:268px;'
        'border-radius:10px;overflow:hidden;background:radial-gradient(circle at 50% 35%,'
        'rgba(94,200,255,.06),transparent 70%);touch-action:none;cursor:grab"></div>'
        f'<div class="bm3d-fallback" style="display:none">{fallback}</div>'
    )

    legend = (
        '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:11px;'
        'color:var(--text-dim,#9ba3b4)">'
        '<span><span style="color:var(--warn,#ffb86b)">●</span> joint (fulcrum)</span>'
        '<span><span style="color:var(--good,#67e8b0)">▬</span> forearm (lever)</span>'
        '<span><span style="color:var(--accent,#5ec8ff)">→</span> muscle force</span>'
        '<span><span style="color:var(--bad,#ff7a7a)">↓</span> load (gravity)</span>'
        "</div>"
    )

    controls = (
        '<div class="bm-controls">'
        '<label>Elbow angle: <b id="__UID__-anglbl">90°</b> &nbsp;·&nbsp; drag the model to rotate it</label>'
        '<input type="range" min="0" max="170" step="2" value="90" id="__UID__-sl" class="bm-slider">'
        '<div class="bm-read">Load moment arm: <b id="__UID__-mm">max</b> '
        '&nbsp;|&nbsp; muscle force demand: <b id="__UID__-mf">100%</b></div>'
        "</div>"
    )

    reveal = (
        "<b>3rd-class lever, viewed in 3D.</b> The blue muscle-force arrow inserts "
        "<i>close</i> to the joint (short effort arm); the red load hangs out at the hand "
        "(long load arm). "
        "<span class='bm-why'>Why it matters:</span> spin it and sweep the angle — the load's "
        "moment arm (its horizontal offset from the joint) peaks when the forearm is "
        "horizontal, so the muscle's force demand peaks there too. Same physics as the 2D "
        "torque tool, now in space: force disadvantage bought in exchange for speed and reach."
    )

    three_js = r'''
<script>(function(){
  var root=document.getElementById("__UID__");if(!root)return;
  var stage=root.querySelector(".bm3d-stage"),
      fb=root.querySelector(".bm3d-fallback"),
      sl=root.querySelector("#__UID__-sl");
  function fail(){ if(stage)stage.style.display="none"; if(fb)fb.style.display="block"; }
  function cssv(n,d){try{var v=getComputedStyle(root).getPropertyValue(n).trim();return v||d;}catch(e){return d;}}
  if(!window.WebGLRenderingContext){fail();return;}
  import("https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js")
    .then(function(THREE){ build(THREE); })
    .catch(fail);

  function build(THREE){
    var W=stage.clientWidth||320, H=268, renderer;
    try{
      renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
    }catch(e){fail();return;}
    renderer.setSize(W,H);renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
    stage.appendChild(renderer.domElement);

    var scene=new THREE.Scene();
    var cam=new THREE.PerspectiveCamera(42,W/H,0.1,100);
    cam.position.set(0.9,0.5,4.6);cam.lookAt(0,0.15,0);
    scene.add(new THREE.AmbientLight(0xffffff,1.15));
    var dl=new THREE.DirectionalLight(0xffffff,1.7);dl.position.set(3,6,5);scene.add(dl);
    var fillL=new THREE.DirectionalLight(0xffffff,0.6);fillL.position.set(-4,2,-5);scene.add(fillL);

    function col(v){var c=new THREE.Color();try{c.set(v);}catch(e){c.set('#5ec8ff');}return c;}
    var cAccent=col(cssv('--accent','#5ec8ff')),
        cGood=col(cssv('--good','#67e8b0')),
        cWarn=col(cssv('--warn','#ffb86b')),
        cBad=col(cssv('--bad','#ff7a7a')),
        cBone=col(cssv('--text-dim','#9ba3b4'));

    var group=new THREE.Group();scene.add(group);
    var Lf=1.5; // forearm length

    // upper arm (fixed, vertical from elbow up)
    var ua=new THREE.Mesh(new THREE.CylinderGeometry(0.08,0.08,1.25,20),
        new THREE.MeshStandardMaterial({color:cBone,roughness:.7}));
    ua.position.y=0.625;group.add(ua);
    // shoulder + elbow joints
    var jMat=new THREE.MeshStandardMaterial({color:cWarn,roughness:.5,metalness:.1});
    var shoulder=new THREE.Mesh(new THREE.SphereGeometry(0.12,24,24),jMat);shoulder.position.y=1.25;group.add(shoulder);
    var elbow=new THREE.Mesh(new THREE.SphereGeometry(0.14,24,24),jMat);group.add(elbow);

    // forearm pivot (rotates about Z at the elbow/origin)
    var pivot=new THREE.Group();group.add(pivot);
    var fa=new THREE.Mesh(new THREE.CylinderGeometry(0.07,0.07,Lf,20),
        new THREE.MeshStandardMaterial({color:cGood,roughness:.6}));
    fa.position.y=-Lf/2;pivot.add(fa);
    var hand=new THREE.Mesh(new THREE.SphereGeometry(0.1,20,20),
        new THREE.MeshStandardMaterial({color:cGood,roughness:.6}));
    hand.position.y=-Lf;pivot.add(hand);

    // arrows (rebuilt each frame for direction/length)
    var loadArrow=null, muscleArrow=null, momentLine=null;
    function clearHelper(h){ if(h){group.remove(h); if(h.dispose)h.dispose();} }

    function setAngle(deg){
      var a=deg*Math.PI/180;
      pivot.rotation.z=a;
      // analytic hand position (pivot child (0,-Lf,0) rotated by a about Z)
      var hx=Lf*Math.sin(a), hy=-Lf*Math.cos(a);
      // load arrow: straight down from the hand
      clearHelper(loadArrow);
      loadArrow=new THREE.ArrowHelper(new THREE.Vector3(0,-1,0),
        new THREE.Vector3(hx,hy,0),0.55,cBad.getHex(),0.18,0.12);
      group.add(loadArrow);
      // muscle insertion near elbow on the forearm: local (0,-0.4,0)
      var ix=0.4*Math.sin(a), iy=-0.4*Math.cos(a);
      var origin=new THREE.Vector3(0,0.95,0); // upper-arm muscle origin
      var dir=new THREE.Vector3(origin.x-ix,origin.y-iy,0).normalize();
      clearHelper(muscleArrow);
      muscleArrow=new THREE.ArrowHelper(dir,new THREE.Vector3(ix,iy,0),0.7,cAccent.getHex(),0.16,0.1);
      group.add(muscleArrow);
      // moment-arm: horizontal segment from elbow(0,hy) to (hx,hy)
      clearHelper(momentLine);
      var g=new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0,hy,0),new THREE.Vector3(hx,hy,0)]);
      momentLine=new THREE.Line(g,new THREE.LineBasicMaterial({color:cAccent}));
      group.add(momentLine);
      // readouts
      var ratio=Math.abs(Math.sin(a));
      root.querySelector("#__UID__-anglbl").textContent=deg+"°";
      root.querySelector("#__UID__-mm").textContent=Math.round(ratio*100)+"% of max";
      root.querySelector("#__UID__-mf").textContent=Math.round(ratio*100)+"%";
    }
    setAngle(+sl.value);
    sl.addEventListener("input",function(){setAngle(+sl.value);});

    // pointer-drag rotate (no OrbitControls in core three)
    var drag=false,px=0,py=0;
    group.rotation.y=-0.35;
    stage.addEventListener("pointerdown",function(e){drag=true;px=e.clientX;py=e.clientY;stage.style.cursor="grabbing";stage.setPointerCapture&&stage.setPointerCapture(e.pointerId);});
    stage.addEventListener("pointermove",function(e){if(!drag)return;group.rotation.y+=(e.clientX-px)*0.01;group.rotation.x+=(e.clientY-py)*0.008;group.rotation.x=Math.max(-0.9,Math.min(0.9,group.rotation.x));px=e.clientX;py=e.clientY;});
    function endDrag(){drag=false;stage.style.cursor="grab";}
    stage.addEventListener("pointerup",endDrag);stage.addEventListener("pointerleave",endDrag);

    function onResize(){var w=stage.clientWidth||W;renderer.setSize(w,H);cam.aspect=w/H;cam.updateProjectionMatrix();}
    window.addEventListener("resize",onResize);

    var t0=performance.now();
    (function loop(){
      requestAnimationFrame(loop);
      if(!drag){group.rotation.y+=0.0028;} // gentle idle spin
      renderer.render(scene,cam);
    })();
  }
})();</script>'''

    body = (
        biomech._PREDICT_CSS
        + stage
        + legend
        + controls
        + biomech._predict_block(
            "This is a third-class lever (the elbow). As you sweep it through its range, "
            "<b>where is the muscle's force demand highest?</b>",
            [
                ("Near full extension (forearm hanging down)", False),
                ("With the forearm horizontal (~90°)", True),
                ("It's constant throughout the range", False),
            ],
            reveal,
        ).replace(biomech._PREDICT_CSS, "")  # CSS already emitted above
        + three_js
    )
    return biomech._shell(uid, "3D lever lab — bones, joints &amp; force vectors", body, icon="\U0001f9be")


BIOMECH3D = {
    "biomech_levers": [lever_3d],
}


def render(topic_id: str) -> str:
    fns = BIOMECH3D.get(topic_id)
    if not fns:
        return ""
    return "\n".join(fn() for fn in fns)
