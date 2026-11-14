"""Color math: hex text, mixing, and the OKLCH space the generator works in.

OKLCH (lightness, chroma, hue) is perceptual: two colors with the same
lightness look equally bright, which RGB and HSL do not give. Formulas are
Björn Ottosson's Oklab.
"""
import math


def parse(text):
	"""`#rrggbb` (an alpha part is dropped) to (r, g, b), each 0 to 255."""
	return tuple(int(text[i:i + 2], 16) for i in (1, 3, 5))


def fmt(rgb):
	return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def csv(text):
	"""`#0c0b13` to `12,11,19` (how KDE writes colors)."""
	return ",".join(str(c) for c in parse(text))


def mix(a, b, t):
	"""The color `t` of the way from a to b (0 = a, 1 = b), in plain RGB."""
	return fmt(x + (y - x) * t for x, y in zip(parse(a), parse(b)))


def _linear(c):
	c /= 255
	return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c):
	return 255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)


def to_oklch(text):
	"""Returns (lightness 0-1, chroma from 0 to about 0.37, hue in degrees)."""
	r, g, b = (_linear(c) for c in parse(text))
	l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
	m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
	s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
	light = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
	a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
	b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
	return light, math.hypot(a, b2), math.degrees(math.atan2(b2, a)) % 360


def _rgb(light, chroma, hue):
	a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
	l_ = (light + 0.3963377774 * a + 0.2158037573 * b) ** 3
	m_ = (light - 0.1055613458 * a - 0.0638541728 * b) ** 3
	s_ = (light - 0.0894841775 * a - 1.2914855480 * b) ** 3
	return (
		4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
		-1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
		-0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
	)


def from_oklch(light, chroma, hue):
	"""Hex text for an OKLCH color. A color the screen can't show keeps its
	lightness and hue and loses chroma until it fits."""
	light = max(0.0, min(1.0, light))

	def fits(c):
		return all(-0.0005 <= v <= 1.0005 for v in _rgb(light, c, hue))

	if not fits(chroma):
		low, high = 0.0, chroma
		for _ in range(20):
			mid = (low + high) / 2
			low, high = (mid, high) if fits(mid) else (low, mid)
		chroma = low
	return fmt(_gamma(max(0.0, min(1.0, v))) for v in _rgb(light, chroma, hue))
