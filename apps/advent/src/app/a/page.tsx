'use client';

import React, { useEffect, useRef } from 'react';
import { gsap } from 'gsap';

import aws1 from "@/assets/landingassets/aws1.png";
import aws2 from "@/assets/landingassets/aws2.png";
import oracle1 from "@/assets/landingassets/oracle1.png";
import gcp1 from "@/assets/landingassets/gcp1.png";
import azure1 from "@/assets/landingassets/azure1.png";

export default function BlackHolePage() {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const overlayRef = useRef<HTMLDivElement>(null);
    const animationRef = useRef<number>(0);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let width: number, height: number;
        let centerX: number, centerY: number;
        const blackHoleRadius = 50;

        // Declare stars array first
        let stars: Array<{
            x: number;
            y: number;
            size: number;
            alpha: number;
        }> = [];

        function generateStars() {
            stars = [];
            for (let i = 0; i < 500; i++) {
                stars.push({
                    x: Math.random() * width,
                    y: Math.random() * height,
                    size: Math.random() * 1 + 0.5,
                    alpha: Math.random() * 0.5 + 0.5,
                });
            }
        }

        function resize() {
            width = window.innerWidth;
            height = window.innerHeight;
            canvas.width = width;
            canvas.height = height;
            centerX = width / 2;
            centerY = height / 2;
            generateStars();
            particles.forEach((p) => p.reset());
        }

        // Particle class for planets
        class Particle {
            image: HTMLImageElement;
            x: number;
            y: number;
            size: number;
            alpha: number;
            rotation: number;
            spinSpeed: number;
            angle: number;
            distance: number;
            speed: number;
            angularSpeed: number;
            trail: Array<{
                x: number;
                y: number;
                rotation: number;
                size: number;
                alpha: number;
            }>;
            trailLength: number;

            constructor(image: HTMLImageElement) {
                this.image = image;
                this.x = 0;
                this.y = 0;
                this.size = 0;
                this.alpha = 1;
                this.rotation = 0;
                this.spinSpeed = 0;
                this.angle = 0;
                this.distance = 0;
                this.speed = 0;
                this.angularSpeed = 0;
                this.trail = [];
                this.trailLength = 20;
                this.reset();
            }

            reset() {
                this.x = Math.random() * width;
                this.y = Math.random() * height;
                this.size = Math.random() * 40 + 20;
                this.alpha = 1;
                this.rotation = Math.random() * Math.PI * 2;
                this.spinSpeed = (Math.random() - 0.5) * 0.1;
                this.angle = Math.random() * Math.PI * 2;
                this.distance = Math.sqrt(
                    (this.x - centerX) ** 2 + (this.y - centerY) ** 2
                );
                this.speed = Math.random() * 0.005 + 0.01;
                this.angularSpeed = Math.random() * 0.02 + 0.01;
                this.trail = [];
                this.trailLength = 20;
            }

            update() {
                // Gravitational pull: reduce distance over time
                this.distance *= 1 - this.speed * (blackHoleRadius / this.distance);

                // Spiral motion
                this.angle += this.angularSpeed * (blackHoleRadius / this.distance);

                // Planet spin
                this.rotation += this.spinSpeed;

                // Update position based on polar coordinates
                this.x = centerX + Math.cos(this.angle) * this.distance;
                this.y = centerY + Math.sin(this.angle) * this.distance;

                // Distortion near black hole: scale down and fade
                if (this.distance < blackHoleRadius * 3) {
                    this.size *= 0.98;
                    this.alpha *= 0.99;
                }

                // Add to trail
                this.trail.push({
                    x: this.x,
                    y: this.y,
                    rotation: this.rotation,
                    size: this.size,
                    alpha: this.alpha,
                });
                if (this.trail.length > this.trailLength) {
                    this.trail.shift();
                }

                // Reset if swallowed
                if (
                    this.distance < blackHoleRadius ||
                    this.size < 5 ||
                    this.alpha < 0.1
                ) {
                    this.reset();
                }
            }

            draw() {
                // Draw trail
                this.trail.forEach((point, i) => {
                    ctx.save();
                    ctx.globalAlpha = (i / this.trailLength) * point.alpha;
                    ctx.translate(point.x, point.y);
                    ctx.rotate(point.rotation);
                    const trailSize = point.size * ((i / this.trailLength) * 0.5 + 0.5);
                    ctx.drawImage(
                        this.image,
                        -trailSize / 2,
                        -trailSize / 2,
                        trailSize,
                        trailSize
                    );
                    ctx.restore();
                });

                // Draw main planet
                ctx.save();
                ctx.globalAlpha = this.alpha;
                ctx.translate(this.x, this.y);
                ctx.rotate(this.rotation);
                ctx.drawImage(
                    this.image,
                    -this.size / 2,
                    -this.size / 2,
                    this.size,
                    this.size
                );
                ctx.restore();
            }
        }

        const particles: Particle[] = [];
        const planetUrls = [
            aws1,
            //aws2,
            oracle1,
            gcp1,
            azure1,
        ];

        // Load images independently and create particles on success
        planetUrls.forEach((url) => {
            const img = new Image();
            img.crossOrigin = "anonymous";
            img.src = url.src;
            img.onload = () => {
                // Create up to 2 particles per image to reach up to 8
                for (let i = 0; i < 2; i++) {
                    if (particles.length < 8) {
                        particles.push(new Particle(img));
                    }
                }
            };
            img.onerror = () => {
                console.error(`Failed to load image: ${url}`);
            };
        });

        // Accretion disk simulation
        function drawBlackHole() {
            // Event horizon
            const gradient = ctx.createRadialGradient(
                centerX,
                centerY,
                0,
                centerX,
                centerY,
                blackHoleRadius * 2
            );
            gradient.addColorStop(0, "black");
            gradient.addColorStop(0.5, "rgba(0,0,0,0.8)");
            gradient.addColorStop(1, "rgba(255,165,0,0.2)"); // Orange glow for accretion

            ctx.beginPath();
            ctx.arc(centerX, centerY, blackHoleRadius * 2, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();

            // Pulsing glow
            const pulse = Math.sin(Date.now() / 2000) * 0.1 + 1;
            const glowRadius = blackHoleRadius * 2 * pulse;
            const glowGradient = ctx.createRadialGradient(
                centerX,
                centerY,
                blackHoleRadius,
                centerX,
                centerY,
                glowRadius
            );
            glowGradient.addColorStop(0, "rgba(255,165,0,0.3)");
            glowGradient.addColorStop(1, "rgba(255,165,0,0)");
            ctx.beginPath();
            ctx.arc(centerX, centerY, glowRadius, 0, Math.PI * 2);
            ctx.fillStyle = glowGradient;
            ctx.fill();
        }

        function animate() {
            ctx.clearRect(0, 0, width, height);

            // Draw starry background
            stars.forEach((s) => {
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255,255,255,${s.alpha})`;
                ctx.fill();
            });

            drawBlackHole();

            particles.forEach((p) => {
                p.update();
                p.draw();
            });

            animationRef.current = requestAnimationFrame(animate);
        }

        // Initialize everything
        resize();
        const handleResize = () => resize();
        window.addEventListener("resize", handleResize);

        // Start animation
        animate();

        // GSAP animation for overlay
        if (overlayRef.current) {
            gsap.from(overlayRef.current, {
                opacity: 0,
                y: 50,
                duration: 2,
                delay: 1
            });
        }

        // Add button functionality
        const handleExploreClick = () => {
            particles.forEach((p) => p.reset());
        };

        const exploreBtn = document.getElementById("explore-btn");
        if (exploreBtn) {
            exploreBtn.addEventListener("click", handleExploreClick);
        }

        // Cleanup function
        return () => {
            window.removeEventListener("resize", handleResize);
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current);
            }
            if (exploreBtn) {
                exploreBtn.removeEventListener("click", handleExploreClick);
            }
        };
    }, []);

    return (
        <div className="relative w-full h-screen overflow-hidden bg-black">
            <canvas
                ref={canvasRef}
                className="block"
            />
            <div
                ref={overlayRef}
                className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center z-10 text-white"
            >
                <h1 className="text-5xl font-bold mb-4">Enter the Void</h1>
                <p className="text-xl mb-6">Witness the power of gravitational innovation.</p>
                <button
                    id="explore-btn"
                    className="px-6 py-3 bg-blue-600 rounded-lg hover:bg-blue-700 transition"
                >
                    Explore Now
                </button>
            </div>
        </div>
    );
}