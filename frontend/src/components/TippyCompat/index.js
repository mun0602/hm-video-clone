/**
 * TippyCompat — wrapper quanh @tippyjs/react@4.2.6 fix React 19 incompatibility.
 *
 * Issue: @tippyjs/react@4.x internally accesses `element.ref` (kiểu React ≤18).
 * React 19 removed this — `ref` is now a regular prop, not a property on element.
 *
 * Workaround: wrap children in <div ref={tippyRef}> và pass `reference` prop cho Tippy
 * thay vì để Tippy tự access `children.ref`. Điều này bypass React 19 removal.
 *
 * @example
 *   <TippyCompat content="Hello">
 *     <button>Click me</button>
 *   </TippyCompat>
 */
import { forwardRef, useRef, useImperativeHandle } from 'react';
import Tippy from '@tippyjs/react';
import HeadlessTippy from '@tippyjs/react/headless';

function TippyCompatInner(
  { children, headless = false, ...props },
  forwardedRef,
) {
  const wrapperRef = useRef(null);

  // Expose wrapper ref cho parent
  useImperativeHandle(forwardedRef, () => wrapperRef.current, []);

  // Truyền wrapperRef qua prop `reference` — Tippy dùng nó thay vì tự access children.ref
  const Component = headless ? HeadlessTippy : Tippy;

  return (
    <Component {...props} reference={wrapperRef}>
      <span ref={wrapperRef} style={{ display: 'inline-block' }}>
        {children}
      </span>
    </Component>
  );
}

const TippyCompat = forwardRef(TippyCompatInner);

// Re-export Headless variant
export const HeadlessTippyCompat = forwardRef(function HeadlessTippyCompatC(
  { children, ...props },
  ref,
) {
  return (
    <TippyCompat ref={ref} headless {...props}>
      {children}
    </TippyCompat>
  );
});

export default TippyCompat;
