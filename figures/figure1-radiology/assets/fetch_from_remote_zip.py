"""Extract selected members from a huge remote ZIP via HTTP range requests."""
import io, struct, sys, zlib, os, json, re
import requests

class RemoteZip:
    def __init__(self, url):
        self.url = url
        h = requests.head(url, allow_redirects=True, timeout=60)
        self.url = h.url
        self.size = int(h.headers["content-length"])
        self.cd = None

    def _get(self, start, length):
        end = start + length - 1
        r = requests.get(self.url, headers={"Range": f"bytes={start}-{end}"}, timeout=180)
        r.raise_for_status()
        return r.content

    def load_central_directory(self):
        tail_n = min(self.size, 1 << 16)
        tail = self._get(self.size - tail_n, tail_n)
        i = tail.rfind(b"PK\x05\x06")
        if i < 0:
            raise RuntimeError("no EOCD")
        cd_size, cd_off = struct.unpack("<II", tail[i + 12:i + 20])
        if cd_off == 0xFFFFFFFF or cd_size == 0xFFFFFFFF:      # zip64
            j = tail.rfind(b"PK\x06\x07")
            z64_eocd_off = struct.unpack("<Q", tail[j + 8:j + 16])[0]
            z64 = self._get(z64_eocd_off, 56)
            assert z64[:4] == b"PK\x06\x06"
            cd_size, cd_off = struct.unpack("<QQ", z64[40:56])
        print(f"  central directory: {cd_size/1e6:.1f} MB at offset {cd_off}", file=sys.stderr)
        self.cd = self._get(cd_off, cd_size)

    def entries(self):
        buf, p = self.cd, 0
        while p < len(buf) - 4 and buf[p:p+4] == b"PK\x01\x02":
            (method, csize, usize, nlen, elen, clen) = (
                struct.unpack("<H", buf[p+10:p+12])[0],
                struct.unpack("<I", buf[p+20:p+24])[0],
                struct.unpack("<I", buf[p+24:p+28])[0],
                struct.unpack("<H", buf[p+28:p+30])[0],
                struct.unpack("<H", buf[p+30:p+32])[0],
                struct.unpack("<H", buf[p+32:p+34])[0])
            lho = struct.unpack("<I", buf[p+42:p+46])[0]
            name = buf[p+46:p+46+nlen].decode("utf-8", "replace")
            extra = buf[p+46+nlen:p+46+nlen+elen]
            if 0xFFFFFFFF in (csize, usize, lho):               # zip64 extra field
                q = 0
                while q < len(extra) - 4:
                    tag, sz = struct.unpack("<HH", extra[q:q+4])
                    if tag == 0x0001:
                        vals, r = [], q + 4
                        for orig in (usize, csize, lho):
                            if orig == 0xFFFFFFFF:
                                vals.append(struct.unpack("<Q", extra[r:r+8])[0]); r += 8
                            else:
                                vals.append(orig)
                        usize, csize, lho = vals
                        break
                    q += 4 + sz
            yield {"name": name, "method": method, "csize": csize,
                   "usize": usize, "lho": lho}
            p += 46 + nlen + elen + clen

    def extract(self, e, dest):
        head = self._get(e["lho"], 30)
        assert head[:4] == b"PK\x03\x04", "bad local header"
        nlen, elen = struct.unpack("<HH", head[26:30])
        data = self._get(e["lho"] + 30 + nlen + elen, e["csize"])
        if e["method"] == 8:
            data = zlib.decompress(data, -15)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
        return len(data)


if __name__ == "__main__":
    url, pattern, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else 999
    cache = os.path.join(outdir, "_cd.bin")
    rz = RemoteZip(url)
    if os.path.exists(cache):
        rz.cd = open(cache, "rb").read()
        print("  (central directory from cache)", file=sys.stderr)
    else:
        rz.load_central_directory()
        os.makedirs(outdir, exist_ok=True)
        open(cache, "wb").write(rz.cd)
    rx = re.compile(pattern)
    n = 0
    for e in rz.entries():
        if e["usize"] == 0 or not rx.search(e["name"]):
            continue
        dest = os.path.join(outdir, e["name"])
        if os.path.exists(dest):
            print(f"  skip (have) {e['name']}"); n += 1; continue
        sz = rz.extract(e, dest)
        print(f"  {e['name']}  {sz/1e6:.2f} MB")
        n += 1
        if n >= limit:
            break
    print(f"extracted/found {n} files")
