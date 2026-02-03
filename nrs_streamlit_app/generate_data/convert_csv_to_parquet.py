import pandas as pd
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

# ---------------- CONFIG ----------------
# Folder where CSVs live
input_dir = Path("/home/babayemi-mercy/projects/NRS/nrs_streamlit_app/generate_data/output")

# Folder to save Parquet files
output_dir = Path("/home/babayemi-mercy/projects/NRS/nrs_streamlit_app/generate_data/parquet")
output_dir.mkdir(parents=True, exist_ok=True)

# Chunk size for large CSVs
CHUNK_SIZE = 200_000

# ---------------- SCRIPT ----------------
csv_files = list(input_dir.glob("*.csv"))
if not csv_files:
    print("No CSV files found in:", input_dir)
else:
    for csv_file in csv_files:
        print(f"Processing {csv_file.name}...")

        # Check file size
        if csv_file.stat().st_size > 100_000_000:  # >100MB
            # Use chunked processing
            print("Large file detected, using chunked processing...")
            writer = None
            for chunk in pd.read_csv(csv_file, chunksize=CHUNK_SIZE):
                table = pa.Table.from_pandas(chunk, preserve_index=False)
                if writer is None:
                    parquet_file = output_dir / csv_file.with_suffix(".parquet").name
                    writer = pq.ParquetWriter(parquet_file, table.schema, compression="snappy")
                writer.write_table(table)
            writer.close()
        else:
            # Small/medium file, load at once
            df = pd.read_csv(csv_file)
            parquet_file = output_dir / csv_file.with_suffix(".parquet").name
            df.to_parquet(parquet_file, compression="snappy", index=False)

        print(f"✅ {csv_file.name} converted to {parquet_file.name}")

print("🎉 All CSVs processed successfully!")
