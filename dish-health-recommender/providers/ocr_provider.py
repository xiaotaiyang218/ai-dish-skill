from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ProviderResult:
    provider_name: str
    status: str
    latency_ms: int
    raw_result: dict[str, Any]
    text: str = ''
    lines: list[str] | None = None
    error_message: str = ''
    credential_hint: str = ''
    degrade_strategy: str = ''

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['lines'] = self.lines or []
        return data


class OCRProvider:
    provider_name = 'base_ocr'

    def recognize(self, image_path: str) -> ProviderResult:
        raise NotImplementedError


class MacVisionOCRProvider(OCRProvider):
    provider_name = 'mac_vision_ocr'

    def recognize(self, image_path: str) -> ProviderResult:
        start = time.time()
        swift_source = r'''
import Foundation
import Vision
import AppKit
let path = CommandLine.arguments[1]
let url = URL(fileURLWithPath: path)
let data = try Data(contentsOf: url)
let image = NSImage(data: data)!
var rect = NSRect(origin: .zero, size: image.size)
let cg = image.cgImage(forProposedRect: &rect, context: nil, hints: nil)!
let req = VNRecognizeTextRequest()
req.recognitionLanguages = ["zh-Hans", "en-US"]
req.recognitionLevel = .accurate
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try handler.perform([req])
let obs = req.results ?? []
var items: [String] = []
for o in obs {
  if let c = o.topCandidates(1).first { items.append(c.string) }
}
print(items.joined(separator: "\n"))
'''
        try:
            with tempfile.NamedTemporaryFile('w', suffix='.swift', delete=False) as f:
                f.write(swift_source)
                tmp = f.name
            proc = subprocess.run(['swift', tmp, image_path], text=True, capture_output=True, check=True)
            text = proc.stdout.strip()
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return ProviderResult(self.provider_name, 'validated', int((time.time() - start) * 1000), {'engine': 'Vision'}, text, lines)
        except Exception as exc:
            return ProviderResult(self.provider_name, 'degraded', int((time.time() - start) * 1000), {'engine': 'Vision'}, '', [], str(exc), '', 'fall back to image labels / manual review')


class DomesticOCRProvider(OCRProvider):
    provider_name = 'domestic_ocr_api'

    def _parse_lines(self, raw: dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        for key in ('lines', 'texts', 'words_result'):
            value = raw.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        candidates.append(item.strip())
                    elif isinstance(item, dict):
                        text = str(item.get('text') or item.get('words') or item.get('content') or '').strip()
                        if text:
                            candidates.append(text)
        if not candidates:
            text = str(raw.get('text') or raw.get('full_text') or raw.get('result') or '').strip()
            if text:
                candidates.extend(line.strip() for line in text.splitlines() if line.strip())
        unique: list[str] = []
        for item in candidates:
            if item not in unique:
                unique.append(item)
        return unique

    def recognize(self, image_path: str) -> ProviderResult:
        start = time.time()
        api_key = os.getenv('DOMESTIC_OCR_API_KEY', '').strip()
        endpoint = os.getenv('DOMESTIC_OCR_ENDPOINT', '').strip()
        if not api_key or not endpoint:
            return ProviderResult(
                self.provider_name,
                'needs_credentials',
                int((time.time() - start) * 1000),
                {},
                '',
                [],
                '',
                'set DOMESTIC_OCR_ENDPOINT and DOMESTIC_OCR_API_KEY',
                'fallback to local mac vision OCR',
            )
        try:
            image_bytes = open(image_path, 'rb').read()
            payload = json.dumps({'image_base64': base64.b64encode(image_bytes).decode('utf-8')}).encode('utf-8')
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}',
                    'X-API-Key': api_key,
                },
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = json.loads(response.read().decode('utf-8'))
            lines = self._parse_lines(raw)
            text = '\n'.join(lines)
            status = 'validated' if lines else 'degraded'
            return ProviderResult(
                self.provider_name,
                status,
                int((time.time() - start) * 1000),
                raw,
                text,
                lines,
                '' if lines else 'domestic OCR response did not contain usable text',
                '',
                'fallback to local mac vision OCR',
            )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='ignore')
            status = 'needs_credentials' if exc.code in {401, 403} else 'degraded'
            hint = 'verify DOMESTIC_OCR_API_KEY or endpoint authorization' if status == 'needs_credentials' else ''
            return ProviderResult(
                self.provider_name,
                status,
                int((time.time() - start) * 1000),
                {'http_status': exc.code, 'response_body': body},
                '',
                [],
                f'HTTP {exc.code}',
                hint,
                'fallback to local mac vision OCR',
            )
        except Exception as exc:
            return ProviderResult(
                self.provider_name,
                'degraded',
                int((time.time() - start) * 1000),
                {'endpoint': endpoint},
                '',
                [],
                str(exc),
                '',
                'fallback to local mac vision OCR',
            )


def get_ocr_providers() -> list[OCRProvider]:
    return [DomesticOCRProvider(), MacVisionOCRProvider()]


def recognize_image_text(image_path: str) -> ProviderResult:
    results = [provider.recognize(image_path) for provider in get_ocr_providers()]
    for result in results:
        if result.status == 'validated' and result.text:
            return result
    for result in results:
        if result.provider_name == 'mac_vision_ocr':
            return result
    return results[0] if results else ProviderResult('none', 'unavailable', 0, {}, error_message='no OCR providers configured')
