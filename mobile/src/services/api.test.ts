import { describe, expect, it } from 'bun:test';
import { parseStudioLink, KeelwayError } from './api';
import { strings, languages, isRTL, type Lang } from '../i18n';

describe('mobile api service: parseStudioLink', () => {
  it('parses valid studio link with token query parameter', () => {
    const conn = parseStudioLink('http://192.168.1.105:7420/?token=abc_secret_123');
    expect(conn).not.toBeNull();
    expect(conn?.baseUrl).toBe('http://192.168.1.105:7420');
    expect(conn?.token).toBe('abc_secret_123');
  });

  it('parses localhost link without token', () => {
    const conn = parseStudioLink('http://localhost:7420/');
    expect(conn).not.toBeNull();
    expect(conn?.baseUrl).toBe('http://localhost:7420');
    expect(conn?.token).toBe('');
  });

  it('parses encoded tokens properly', () => {
    const conn = parseStudioLink('http://keelway.local:7420?foo=1&token=sec%2Bval%3D42&bar=2');
    expect(conn).not.toBeNull();
    expect(conn?.baseUrl).toBe('http://keelway.local:7420');
    expect(conn?.token).toBe('sec+val=42');
  });

  it('rejects invalid or non-http links', () => {
    expect(parseStudioLink('ftp://192.168.1.1:7420')).toBeNull();
    expect(parseStudioLink('not a link at all')).toBeNull();
    expect(parseStudioLink('')).toBeNull();
  });
});

describe('mobile error handling: KeelwayError', () => {
  it('encapsulates message and HTTP status code', () => {
    const err = new KeelwayError('Forbidden', 403);
    expect(err.message).toBe('Forbidden');
    expect(err.status).toBe(403);
    expect(err instanceof Error).toBe(true);
  });
});

describe('mobile i18n localization table', () => {
  it('provides all 4 supported languages', () => {
    expect(languages.length).toBe(4);
    const codes = languages.map((l) => l.code);
    expect(codes).toContain('en');
    expect(codes).toContain('sw');
    expect(codes).toContain('fr');
    expect(codes).toContain('ar');
  });

  it('detects RTL correctly for Arabic', () => {
    expect(isRTL('ar')).toBe(true);
    expect(isRTL('en')).toBe(false);
    expect(isRTL('sw')).toBe(false);
    expect(isRTL('fr')).toBe(false);
  });

  it('returns valid string translations for each language', () => {
    for (const l of ['en', 'sw', 'fr', 'ar'] as Lang[]) {
      const s = strings[l];
      expect(s.pairTitle.length).toBeGreaterThan(0);
      expect(s.connect.length).toBeGreaterThan(0);
      expect(s.approve.length).toBeGreaterThan(0);
      expect(s.deny.length).toBeGreaterThan(0);
    }
  });
});

describe('mobile api service: pairing links', () => {
  it('reads the single-use pairing code from keelway mobile pair links', () => {
    const conn = parseStudioLink('http://192.168.1.20:7420/?pair=keelway_pair_abc-123');
    expect(conn?.baseUrl).toBe('http://192.168.1.20:7420');
    expect(conn?.pairCode).toBe('keelway_pair_abc-123');
    expect(conn?.token).toBe('');
  });

  it('has no pairing code on plain token links', () => {
    expect(parseStudioLink('http://192.168.1.20:7420/?token=abc')?.pairCode).toBe('');
  });
});

describe('mobile sha256 + merkle verification', () => {
  const { sha256Hex, verifyMerkleProof } = require('./sha256');

  it('matches published SHA-256 vectors', () => {
    expect(sha256Hex('')).toBe('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
    expect(sha256Hex('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
    expect(sha256Hex('a'.repeat(1000))).toBe('41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3');
  });

  it('folds an inclusion proof the way AuditMerkleTree.verify_proof does', () => {
    // 2-leaf tree: root = sha256(leafA + leafB); proof for A is sibling B on the right.
    const leafA = sha256Hex('entry-a');
    const leafB = sha256Hex('entry-b');
    const root = sha256Hex(leafA + leafB);
    expect(verifyMerkleProof(leafA, [{ direction: 'right', hash: leafB }], root)).toBe(true);
    expect(verifyMerkleProof(leafB, [{ direction: 'left', hash: leafA }], root)).toBe(true);
    expect(verifyMerkleProof(leafA, [{ direction: 'left', hash: leafB }], root)).toBe(false);
    expect(verifyMerkleProof(leafA, [], root)).toBe(false);
  });
});
