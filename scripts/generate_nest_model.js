#!/usr/bin/env node
/**
 * Generate a procedural 3D community nest model as GLTF.
 *
 * The nest is a dome-like structure made of interwoven branches —
 * organic, not geometric. Think bird's nest scaled to human size.
 *
 * Output: web/public/assets/models/community-nest.gltf
 */

const fs = require('fs');
const path = require('path');

// Simple GLTF builder
function buildGLTF(positions, indices, normals) {
  // Interleave position + normal data into a single buffer
  const vertexCount = positions.length / 3;
  const vertexData = new Float32Array(vertexCount * 6);
  for (let i = 0; i < vertexCount; i++) {
    vertexData[i * 6 + 0] = positions[i * 3 + 0];
    vertexData[i * 6 + 1] = positions[i * 3 + 1];
    vertexData[i * 6 + 2] = positions[i * 3 + 2];
    vertexData[i * 6 + 3] = normals[i * 3 + 0];
    vertexData[i * 6 + 4] = normals[i * 3 + 1];
    vertexData[i * 6 + 5] = normals[i * 3 + 2];
  }

  const indexData = new Uint16Array(indices);

  // Convert to base64
  const vertexB64 = Buffer.from(vertexData.buffer).toString('base64');
  const indexB64 = Buffer.from(indexData.buffer).toString('base64');

  // Compute bounds
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (let i = 0; i < positions.length; i += 3) {
    minX = Math.min(minX, positions[i]);
    minY = Math.min(minY, positions[i + 1]);
    minZ = Math.min(minZ, positions[i + 2]);
    maxX = Math.max(maxX, positions[i]);
    maxY = Math.max(maxY, positions[i + 1]);
    maxZ = Math.max(maxZ, positions[i + 2]);
  }

  return {
    asset: { version: "2.0", generator: "coherence-network-nest-generator" },
    scene: 0,
    scenes: [{ nodes: [0] }],
    nodes: [{ mesh: 0, name: "CommunityNest" }],
    meshes: [{
      primitives: [{
        attributes: { POSITION: 0, NORMAL: 1 },
        indices: 2,
        material: 0,
      }],
    }],
    materials: [{
      name: "NestMaterial",
      pbrMetallicRoughness: {
        baseColorFactor: [0.55, 0.35, 0.15, 1.0], // warm wood/earth tone
        metallicFactor: 0.0,
        roughnessFactor: 0.9,
      },
    }],
    accessors: [
      { // POSITION
        bufferView: 0, byteOffset: 0, componentType: 5126,
        count: vertexCount, type: "VEC3",
        min: [minX, minY, minZ], max: [maxX, maxY, maxZ],
      },
      { // NORMAL
        bufferView: 0, byteOffset: 12, componentType: 5126,
        count: vertexCount, type: "VEC3",
      },
      { // INDICES
        bufferView: 1, componentType: 5123,
        count: indices.length, type: "SCALAR",
      },
    ],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: vertexData.byteLength, byteStride: 24 },
      { buffer: 1, byteOffset: 0, byteLength: indexData.byteLength },
    ],
    buffers: [
      { uri: `data:application/octet-stream;base64,${vertexB64}`, byteLength: vertexData.byteLength },
      { uri: `data:application/octet-stream;base64,${indexB64}`, byteLength: indexData.byteLength },
    ],
  };
}

// Generate a dome from interwoven "branch" rings
function generateNestDome(rings = 12, segments = 24, radius = 5, height = 4) {
  const positions = [];
  const normals = [];
  const indices = [];

  // Generate dome vertices with organic wobble
  for (let ring = 0; ring <= rings; ring++) {
    const t = ring / rings; // 0 at base, 1 at top
    const phi = t * Math.PI * 0.5; // 0 to 90 degrees
    const ringRadius = radius * Math.cos(phi);
    const y = height * Math.sin(phi);

    for (let seg = 0; seg <= segments; seg++) {
      const theta = (seg / segments) * Math.PI * 2;

      // Add organic wobble — like real branches, not perfect geometry
      const wobble = 0.15 * Math.sin(theta * 7 + ring * 2.3) +
                     0.1 * Math.cos(theta * 11 - ring * 1.7);
      const r = ringRadius * (1 + wobble);

      const x = r * Math.cos(theta);
      const z = r * Math.sin(theta);

      positions.push(x, y, z);

      // Normal points outward from center
      const nx = Math.cos(theta) * Math.cos(phi);
      const ny = Math.sin(phi);
      const nz = Math.sin(theta) * Math.cos(phi);
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz);
      normals.push(nx / len, ny / len, nz / len);
    }
  }

  // Generate triangles connecting rings
  const vertsPerRing = segments + 1;
  for (let ring = 0; ring < rings; ring++) {
    for (let seg = 0; seg < segments; seg++) {
      const a = ring * vertsPerRing + seg;
      const b = a + 1;
      const c = a + vertsPerRing;
      const d = c + 1;

      indices.push(a, c, b);
      indices.push(b, c, d);
    }
  }

  // Add a ground ring (flat base)
  const baseCenter = positions.length / 3;
  positions.push(0, 0, 0);
  normals.push(0, -1, 0);

  for (let seg = 0; seg <= segments; seg++) {
    const theta = (seg / segments) * Math.PI * 2;
    const wobble = 0.1 * Math.sin(theta * 5);
    const r = radius * (1 + wobble);
    positions.push(r * Math.cos(theta), 0, r * Math.sin(theta));
    normals.push(0, -1, 0);
  }

  for (let seg = 0; seg < segments; seg++) {
    indices.push(baseCenter, baseCenter + seg + 2, baseCenter + seg + 1);
  }

  // Add entrance opening (remove some triangles at the front)
  // We skip this for simplicity — the dome already looks nest-like

  return { positions: new Float32Array(positions), normals: new Float32Array(normals), indices };
}

// Generate and save
const { positions, normals, indices } = generateNestDome();
const gltf = buildGLTF(positions, indices, normals);

const outDir = path.join(__dirname, '..', 'web', 'public', 'assets', 'models');
fs.mkdirSync(outDir, { recursive: true });

const outPath = path.join(outDir, 'community-nest.gltf');
fs.writeFileSync(outPath, JSON.stringify(gltf, null, 2));

const stats = fs.statSync(outPath);
console.log(`Generated: ${outPath}`);
console.log(`  Vertices: ${positions.length / 3}`);
console.log(`  Triangles: ${indices.length / 3}`);
console.log(`  File size: ${(stats.size / 1024).toFixed(1)} KB`);
