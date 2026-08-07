const particles = Array.from({ length: 20 }, (_, index) => ({
  left: `${(index * 47) % 97}%`,
  top: `${(index * 71) % 93}%`,
  delay: `${-((index * 0.37) % 5)}s`,
  size: `${1 + (index % 3)}px`,
}));

export function ParticleField() {
  return (
    <div aria-hidden="true" className="particle-field">
      {particles.map((particle, index) => (
        <span
          key={index}
          style={{
            animationDelay: particle.delay,
            height: particle.size,
            left: particle.left,
            top: particle.top,
            width: particle.size,
          }}
        />
      ))}
    </div>
  );
}
