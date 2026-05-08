from __future__ import annotations

import os
import subprocess
import tempfile
import time
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
            return ProviderResult(self.provider_name, 'validated', int((time.time()-start)*1000), {'engine': 'Vision'}, text, lines)
        except Exception as exc:
            return ProviderResult(self.provider_name, 'degraded', int((time.time()-start)*1000), {'engine': 'Vision'}, '', [], str(exc), '', 'fall back to image labels / manual review')


class DomesticOCRProvider(OCRProvider):
    provider_name = 'domestic_ocr_api'

    def recognize(self, image_path: str) -> ProviderResult:
        start = time.time()
        api_key = os.getenv('DOMESTIC_OCR_API_KEY', '')
        endpoint = os.getenv('DOMESTIC_OCR_ENDPOINT', '')
        if not api_key or not endpoint:
            return ProviderResult(self.provider_name, 'needs_credentials', int((time.time()-start)*1000), {}, '', [], '', 'set DOMESTIC_OCR_ENDPOINT and DOMESTIC_OCR_API_KEY', 'fallback to local mac vision OCR')
        return ProviderResult(self.provider_name, 'unavailable', int((time.time()-start)*1000), {'endpoint': endpoint}, '', [], 'network invocation implemented in validate_apis.py', '', 'fallback to local mac vision OCR')


def get_ocr_providers() -> list[OCRProvider]:
    return [MacVisionOCRProvider(), DomesticOCRProvider()]


def recognize_image_text(image_path: str) -> ProviderResult:
    results = [provider.recognize(image_path) for provider in get_ocr_providers()]
    for result in results:
        if result.status == 'validated' and result.text:
            return result
    return results[0] if results else ProviderResult('none', 'unavailable', 0, {}, error_message='no OCR providers configured')
