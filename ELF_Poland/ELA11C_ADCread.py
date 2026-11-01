import numpy as np

def ela11c_adc_read(fn):
    # A teljes fájl beolvasása előjel nélküli 8-bites egész számokként
    raw = np.fromfile(fn, dtype=np.uint8)

    header = raw[:64]
    
    # MATLAB 1-alapú indexelése (49, 50) Pythonban 48 és 49
    first_sample = int(header[48]) * 256 + int(header[49])
    tini = first_sample / 1250e3 - 20e-6

    file_size = len(raw)
    chunks = []

    # 1. A 0. blokk feldolgozása (64-511. bájtok)
    # A 64-es indexű bájtot a MATLAB kód is átugorja, a 65-östől indul 89 minta
    if file_size >= 510:
        chunk0 = raw[65 : 65 + 89*5].reshape(89, 5)
        chunks.append(chunk0)

    # 2. A teljes, 512 bájtos adatblokkok feldolgozása (512. bájttól)
    offset = 512
    num_full_blocks = (file_size - offset) // 512

    if num_full_blocks > 0:
        blocks = raw[offset : offset + num_full_blocks * 512].reshape(num_full_blocks, 512)
        # Minden blokk első 510 bájtja az adat (102 db 5 bájtos minta), a maradék 2 bájt padding
        data_bytes = blocks[:, :510].flatten()
        chunks.append(data_bytes.reshape(-1, 5))

    # 3. Maradék (részleges) blokk feldolgozása a fájl végén
    offset += num_full_blocks * 512
    remaining_bytes = file_size - offset
    if remaining_bytes >= 5:
        usable_bytes = min(remaining_bytes, 510)
        num_samples = usable_bytes // 5
        partial_chunk = raw[offset : offset + num_samples*5].reshape(num_samples, 5)
        chunks.append(partial_chunk)

    # Adatok rekonstrukciója vektorizált bitműveletekkel
    if len(chunks) > 0:
        all_chunks = np.vstack(chunks).astype(np.int32)
        
        # Shiftelés és maszkolás a MATLAB logika alapján
        Bx = (all_chunks[:, 0] >> 2) * 65536 + all_chunks[:, 1] * 256 + all_chunks[:, 2]
        By = (all_chunks[:, 0] & 3) * 65536 + all_chunks[:, 3] * 256 + all_chunks[:, 4]
    else:
        Bx = np.array([])
        By = np.array([])

    # A MATLAB algoritmus levágja a végről azokat a mintákat, ahol bármelyik érték 0.
    valid_indices = np.where((Bx != 0) & (By != 0))[0]
    if len(valid_indices) > 0:
        last_valid = valid_indices[-1]
        Bx = Bx[:last_valid+1]
        By = By[:last_valid+1]
    else:
        Bx = np.array([])
        By = np.array([])

    nr = len(Bx)
    print(f'Number of samples {nr} (fs=3kHz)')

    return Bx, By, nr, tini
