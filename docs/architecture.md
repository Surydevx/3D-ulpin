---
icon: lucide/boxes
---

# Architecture

If you need to debug the computational engines, here is how the math actually works.

## 1. Bayesian Sensor Fusion

Hardware sensors drift. If a drone scans a building at 18.1m and a ground laser says 18.0m, naive averaging is a bad idea. We use inverse-variance weighting to calculate the ground truth.

Given a sensor reading $x_i$ and its known hardware variance $\sigma_i^2$, we weight the reading based on its precision:
$$w_i = \frac{1}{\sigma_i^2}$$

As we iterate through the sensor array, we update the estimated true height ($\hat{\mu}$) and the combined variance ($\hat{\sigma}^2$):
$$\hat{\mu}_{new} = \frac{\hat{\mu}_{old} \cdot \sigma_i^2 + x_i \cdot \hat{\sigma}_{old}^2}{\hat{\sigma}_{old}^2 + \sigma_i^2}$$
$$\hat{\sigma}_{new}^2 = \frac{\hat{\sigma}_{old}^2 \cdot \sigma_i^2}{\hat{\sigma}_{old}^2 + \sigma_i^2}$$

**Outlier Rejection:** Before running the fusion loop, if $N \ge 3$, we grab the median consensus. Any reading further than $2.5\text{m}$ (configurable) from the median is discarded.

## 2. 3D ULPIN Hashing

We need a tamper-evident, deterministic ID for every 3D volume. We build this using a Z-order curve (Morton code).

1. **Spatial Discretization:** We take the floating-point 3D centroid, convert it to a fixed-precision integer grid, and interleave the bits to map the 3D space into a 1D integer index:
   $$M(x, y, z) = \sum_{i=0}^{N-1} (x_i \cdot 2^{3i} + y_i \cdot 2^{3i+1} + z_i \cdot 2^{3i+2})$$
2. **Cryptographic Checksum:** To prevent spoofing, we hash the Morton index, the parent 2D ULPIN, and our `.env` salt using SHA-256. The first 8 characters of this hash become the public ULPIN suffix.

## 3. Volumetric Collision Engine

To mathematically prove two infrastructure parcels ($\mathcal{V}_A$ and $\mathcal{V}_B$) do not collide:
$$\mathcal{V}_A \cap \mathcal{V}_B = \emptyset$$

To save CPU cycles, we short-circuit the math:

1. **Fast Path (1D Z-Axis):** If $\max(Z_{min}^A, Z_{min}^B) < \min(Z_{max}^A, Z_{max}^B)$ evaluates to false, the bounding boxes don't overlap vertically. We exit early and return `VALID`.

2. **Slow Path (2D Intersection):** If the Z-axis overlaps, we compute the 2D polygon intersection. If `Area > 0`, we multiply by the Z-overlap delta to return the exact collision volume in cubic meters.