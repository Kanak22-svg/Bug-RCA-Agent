"""Log & Stack Trace Analyzer.
Parses raw logs, stack traces, and error messages to extract structured RCA signals.
"""
import re
from typing import Optional
from datetime import datetime


class LogAnalyzer:
    """Analyzes raw logs, stack traces, and error output for root cause signals."""

    # Common exception/error patterns
    EXCEPTION_PATTERNS = [
        r"(?P<type>\w+(?:Error|Exception|Fault))\s*:\s*(?P<message>.+)",
        r"(?:raise|throw|panic)\s+(?P<type>\w+)\s*\((?P<message>[^)]+)\)",
        r"(?P<type>FATAL|ERROR|CRITICAL)\s*[:\-]\s*(?P<message>.+)",
    ]

    STACKTRACE_PATTERNS = {
        "python": r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\w+)',
        "java": r"at (?P<package>[\w.]+)\.(?P<class>\w+)\.(?P<func>\w+)\((?P<file>\w+\.java):(?P<line>\d+)\)",
        "javascript": r"at (?:(?P<func>[\w.]+)\s+\()?(?P<file>[^:)]+):(?P<line>\d+):(?P<col>\d+)\)?",
        "go": r"(?P<file>[\w/]+\.go):(?P<line>\d+)\s+\+0x[\da-f]+",
        "csharp": r"at (?P<namespace>[\w.]+)\.(?P<func>\w+)\(.*?\)\s+in\s+(?P<file>[^:]+):line\s+(?P<line>\d+)",
    }

    HTTP_ERROR_PATTERN = r"(?:HTTP|Status)\s*(?:code\s*)?:?\s*(?P<code>[45]\d{2})\s*(?P<reason>\w[\w\s]*)??"
    TIMEOUT_PATTERN = r"(?:timeout|timed?\s*out|deadline\s*exceeded).*?(?:(?P<duration>\d+(?:\.\d+)?)\s*(?:ms|s|seconds|milliseconds))?"
    OOM_PATTERN = r"(?:out\s*of\s*memory|OOM|memory\s*(?:limit|exceeded|allocation\s*failed))"
    CONNECTION_PATTERN = r"(?:connection\s*(?:refused|reset|timeout|closed)|ECONNREFUSED|ECONNRESET|ETIMEDOUT)"

    async def analyze(self, raw_input: str) -> dict:
        """Analyze raw log/error/stacktrace input and extract structured findings."""
        result = {
            "input_type": self._detect_input_type(raw_input),
            "errors": self._extract_errors(raw_input),
            "stack_frames": self._extract_stack_frames(raw_input),
            "http_errors": self._extract_http_errors(raw_input),
            "timeouts": self._extract_timeouts(raw_input),
            "oom_detected": bool(re.search(self.OOM_PATTERN, raw_input, re.IGNORECASE)),
            "connection_errors": self._extract_connection_errors(raw_input),
            "key_files": [],
            "root_cause_hints": [],
            "severity": "unknown",
            "summary": "",
        }

        # Derive key files from stack frames
        result["key_files"] = self._derive_key_files(result["stack_frames"])

        # Generate root cause hints
        result["root_cause_hints"] = self._generate_hints(result)

        # Determine severity
        result["severity"] = self._determine_severity(result)

        # Build summary
        result["summary"] = self._build_summary(result)

        return result

    def _detect_input_type(self, text: str) -> str:
        """Detect whether input is a stack trace, log block, error message, or mixed."""
        has_stack = any(
            re.search(pat, text) for pat in self.STACKTRACE_PATTERNS.values()
        )
        has_timestamps = bool(re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", text))
        has_log_levels = bool(re.search(r"\b(?:DEBUG|INFO|WARN|ERROR|FATAL|CRITICAL)\b", text))

        if has_stack and has_timestamps:
            return "mixed_log_and_stacktrace"
        elif has_stack:
            return "stacktrace"
        elif has_timestamps and has_log_levels:
            return "structured_log"
        elif has_log_levels:
            return "log_fragment"
        else:
            return "error_message"

    def _extract_errors(self, text: str) -> list[dict]:
        """Extract error/exception types and messages."""
        errors = []
        seen = set()
        for pattern in self.EXCEPTION_PATTERNS:
            for m in re.finditer(pattern, text, re.MULTILINE):
                error_type = m.group("type").strip()
                message = m.group("message").strip()
                key = f"{error_type}:{message[:80]}"
                if key not in seen:
                    seen.add(key)
                    errors.append({
                        "type": error_type,
                        "message": message[:500],
                    })
        return errors

    def _extract_stack_frames(self, text: str) -> list[dict]:
        """Extract stack frames from various languages."""
        frames = []
        for lang, pattern in self.STACKTRACE_PATTERNS.items():
            for m in re.finditer(pattern, text):
                frame = {"language": lang}
                frame["file"] = m.group("file") if "file" in m.groupdict() else None
                frame["line"] = int(m.group("line")) if "line" in m.groupdict() and m.group("line") else None
                frame["function"] = m.group("func") if "func" in m.groupdict() else None
                frames.append(frame)
        return frames

    def _extract_http_errors(self, text: str) -> list[dict]:
        """Extract HTTP error codes."""
        errors = []
        for m in re.finditer(self.HTTP_ERROR_PATTERN, text, re.IGNORECASE):
            errors.append({
                "code": int(m.group("code")),
                "reason": (m.group("reason") or "").strip() if m.group("reason") else None,
            })
        return errors

    def _extract_timeouts(self, text: str) -> list[dict]:
        """Extract timeout-related errors."""
        timeouts = []
        for m in re.finditer(self.TIMEOUT_PATTERN, text, re.IGNORECASE):
            timeouts.append({
                "duration": m.group("duration") if "duration" in m.groupdict() and m.group("duration") else None,
                "context": text[max(0, m.start()-40):m.end()+40].strip(),
            })
        return timeouts

    def _extract_connection_errors(self, text: str) -> list[dict]:
        """Extract connection-related errors."""
        errors = []
        for m in re.finditer(self.CONNECTION_PATTERN, text, re.IGNORECASE):
            errors.append({
                "type": m.group(0).strip(),
                "context": text[max(0, m.start()-40):m.end()+40].strip(),
            })
        return errors

    def _derive_key_files(self, frames: list[dict]) -> list[dict]:
        """Derive key files from stack frames, ranked by importance."""
        file_counts = {}
        for frame in frames:
            f = frame.get("file")
            if f and not any(skip in f for skip in [
                "site-packages", "node_modules", "vendor", "stdlib",
                "<frozen", "<module>", "internal/", "runtime/"
            ]):
                if f not in file_counts:
                    file_counts[f] = {
                        "file": f,
                        "line": frame.get("line"),
                        "function": frame.get("function"),
                        "language": frame.get("language"),
                        "occurrences": 0,
                    }
                file_counts[f]["occurrences"] += 1

        return sorted(file_counts.values(), key=lambda x: x["occurrences"], reverse=True)

    def _generate_hints(self, result: dict) -> list[str]:
        """Generate root cause hypothesis hints from analysis."""
        hints = []

        if result["oom_detected"]:
            hints.append("Memory exhaustion detected — check for memory leaks, large allocations, or unbounded caches")

        for timeout in result.get("timeouts", []):
            hints.append(f"Timeout detected — check for slow queries, external service latency, or deadlocks")

        for conn_err in result.get("connection_errors", []):
            hints.append(f"Connection error ({conn_err['type']}) — check if downstream service is running and reachable")

        for http_err in result.get("http_errors", []):
            code = http_err["code"]
            if code == 500:
                hints.append("HTTP 500 — unhandled server-side exception")
            elif code == 502:
                hints.append("HTTP 502 — upstream server returned invalid response, check proxy/backend health")
            elif code == 503:
                hints.append("HTTP 503 — service unavailable, check capacity and health checks")
            elif code == 504:
                hints.append("HTTP 504 — gateway timeout, check upstream response times")
            elif code == 404:
                hints.append("HTTP 404 — resource not found, check routing and URL construction")
            elif code == 403:
                hints.append("HTTP 403 — forbidden, check authentication and authorization logic")
            elif code == 401:
                hints.append("HTTP 401 — unauthorized, check token/credential validity")
            elif 400 <= code < 500:
                hints.append(f"HTTP {code} — client error, check request payload and validation")

        for error in result.get("errors", []):
            etype = error["type"]
            if "NullPointer" in etype or "TypeError" in etype or "AttributeError" in etype:
                hints.append(f"{etype} — null/undefined reference, check for missing initialization or bad data flow")
            elif "Permission" in etype or "Auth" in etype or "Access" in etype:
                hints.append(f"{etype} — authorization/permission issue, check role and access control logic")
            elif "Syntax" in etype or "Parse" in etype:
                hints.append(f"{etype} — malformed input or configuration, check data format")
            elif "IO" in etype or "File" in etype:
                hints.append(f"{etype} — I/O error, check file paths, permissions, and disk space")
            elif "Database" in etype or "SQL" in etype:
                hints.append(f"{etype} — database error, check query syntax, schema, and connection pool")

        if result["key_files"]:
            top = result["key_files"][0]
            hints.append(f"Top suspect file from stack: {top['file']}:{top.get('line', '?')} in {top.get('function', '?')}()")

        if not hints:
            hints.append("No specific pattern detected — manual review of the error context recommended")

        return hints

    def _determine_severity(self, result: dict) -> str:
        """Determine severity from analysis signals."""
        if result["oom_detected"]:
            return "critical"
        if any(e["type"] in ("FATAL", "CRITICAL") for e in result.get("errors", [])):
            return "critical"
        if any(e.get("code", 0) >= 500 for e in result.get("http_errors", [])):
            return "high"
        if result.get("connection_errors"):
            return "high"
        if result.get("timeouts"):
            return "medium"
        if result.get("errors"):
            return "medium"
        return "low"

    def _build_summary(self, result: dict) -> str:
        """Build a one-paragraph summary of findings."""
        parts = []
        input_type = result["input_type"]
        parts.append(f"Analyzed {input_type}.")

        errors = result.get("errors", [])
        if errors:
            types = list(set(e["type"] for e in errors))[:3]
            parts.append(f"Found {len(errors)} error(s): {', '.join(types)}.")

        frames = result.get("stack_frames", [])
        if frames:
            parts.append(f"Extracted {len(frames)} stack frames.")

        key_files = result.get("key_files", [])
        if key_files:
            top = key_files[0]
            parts.append(f"Top suspect: {top['file']}:{top.get('line', '?')}.")

        severity = result.get("severity", "unknown")
        parts.append(f"Severity: {severity}.")

        hints = result.get("root_cause_hints", [])
        if hints:
            parts.append(f"Primary hypothesis: {hints[0]}")

        return " ".join(parts)
