import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "../lib/utils.js";

/**
 * Aceternity UI–inspired card with a radial spotlight that follows the cursor on hover.
 */
export function SpotlightCard({ children, className, onClick, ...props }) {
  const cardRef = useRef(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  return (
    <motion.div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "relative overflow-hidden rounded-xl border border-border bg-card transition-all duration-300",
        onClick && "cursor-pointer",
        className
      )}
      {...props}
    >
      <div
        className="pointer-events-none absolute inset-0 transition-opacity duration-500"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(400px circle at ${mousePos.x}px ${mousePos.y}px, hsl(36 90% 55% / 0.1), transparent 40%)`,
        }}
      />
      <div className="relative">{children}</div>
    </motion.div>
  );
}
