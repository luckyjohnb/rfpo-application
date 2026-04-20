"""Extract U3D 3D model data from a PDF and save as .u3d file."""
import zlib
import re
import sys

def extract_u3d_from_pdf(pdf_path, output_path):
    with open(pdf_path, 'rb') as f:
        data = f.read()

    # Find all objects and their streams
    # Look for the 3D stream object (has /Type /3D /Subtype /U3D)
    text = data.decode('latin-1')
    
    # Find the 3D object with stream
    pattern = r'/Type\s*/3D\s*/Subtype\s*/U3D\s*/Length\s*(\d+)\s*/Filter\s*/FlateDecode\s*>>\s*stream\r?\n'
    match = re.search(pattern, text)
    
    if not match:
        # Try alternate ordering
        pattern = r'/Subtype\s*/U3D[\s\S]*?/Length\s*(\d+)\s*/Filter\s*/FlateDecode\s*>>\s*stream\r?\n'
        match = re.search(pattern, text)
    
    if not match:
        print("Could not find U3D stream in PDF")
        # Debug: show what 3D-related content exists
        for m in re.finditer(r'/3D|/U3D|/Type /3D', text):
            start = max(0, m.start() - 50)
            end = min(len(text), m.end() + 200)
            print(f"  Found at offset {m.start()}: ...{text[start:end]}...")
        return False
    
    stream_length = int(match.group(1))
    stream_start = match.end()
    compressed_data = data[stream_start:stream_start + stream_length]
    
    print(f"Found U3D stream: {stream_length} bytes compressed")
    
    # Decompress
    try:
        u3d_data = zlib.decompress(compressed_data)
        print(f"Decompressed: {len(u3d_data)} bytes")
    except zlib.error as e:
        print(f"Decompression failed: {e}")
        # Try raw deflate
        try:
            u3d_data = zlib.decompress(compressed_data, -15)
            print(f"Decompressed (raw): {len(u3d_data)} bytes")
        except:
            print("Raw deflate also failed")
            return False
    
    # Verify U3D magic bytes (U3D starts with bytes 00 00 00 00 or specific header)
    header_hex = u3d_data[:16].hex()
    print(f"U3D header (hex): {header_hex}")
    
    with open(output_path, 'wb') as f:
        f.write(u3d_data)
    
    print(f"Saved to: {output_path}")
    return True

if __name__ == '__main__':
    pdf_file = sys.argv[1] if len(sys.argv) > 1 else r"naams_site_dump\publications\Section_B_Bracket Components\ASB1224.pdf"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "test_model.u3d"
    extract_u3d_from_pdf(pdf_file, out_file)
