gsap.registerPlugin(SplitText);


let split = SplitText.create(".text", {
    type: "chars, words"
});

gsap.from(split.chars, {
    y: 100,
    autoAlpha: 0,
    stagger: 0.009,
});
