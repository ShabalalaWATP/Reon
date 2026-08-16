const clouds = Array.from({ length: 9 }, (_, index) => ({
  left: `${(index * 31) % 78}%`,
  top: `${(index * 37) % 82}%`,
  width: `${240 + (index % 3) * 130}px`,
  height: `${92 + (index % 4) * 34}px`,
  duration: `${11 + index * 3}s`,
  delay: `${-(index * 5)}s`,
  opacity: 0.6 + (index % 3) * 0.16,
}));

export function CloudField() {
  return (
    <div aria-hidden="true" className="cloud-field">
      {clouds.map((cloud, index) => (
        <span
          key={index}
          style={{
            animationDelay: cloud.delay,
            animationDuration: cloud.duration,
            height: cloud.height,
            left: cloud.left,
            opacity: cloud.opacity,
            top: cloud.top,
            width: cloud.width,
          }}
        />
      ))}
    </div>
  );
}
