const clouds = Array.from({ length: 6 }, (_, index) => ({
  left: `${(index * 31) % 78}%`,
  top: `${(index * 37) % 82}%`,
  width: `${180 + (index % 3) * 95}px`,
  height: `${68 + (index % 4) * 26}px`,
  duration: `${11 + index * 3}s`,
  delay: `${-(index * 5)}s`,
  opacity: 0.45 + (index % 3) * 0.18,
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
