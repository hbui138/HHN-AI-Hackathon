# Save this as: src/extract_test_set.py
import pandas as pd
import glob
from pathlib import Path
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent.parent
master_db_path = BASE_DIR / "preprocessed_data" / "master_database.parquet"
inquiry_dir = BASE_DIR / "customerinquiry"

df_master = pd.read_parquet(master_db_path)
df_master['id'] = df_master['id'].astype(str).str.strip()

inquiry_files = glob.glob(str(inquiry_dir / "*.csv"))
df_inquiries_list = []
for file in inquiry_files:
    df = pd.read_csv(file, on_bad_lines='skip', engine='python')
    # Add a column to track which file this inquiry came from (for filtering later)
    df['category'] = Path(file).name
    df_inquiries_list.append(df)
    
df_inquiry = pd.concat(df_inquiries_list, ignore_index=True)
df_inquiry = df_inquiry.dropna(subset=['articleid_matched', 'CustomerArticleDescription'])
df_inquiry['articleid_matched'] = pd.to_numeric(df_inquiry['articleid_matched'], errors='coerce').fillna(0).astype(int).astype(str)

merged_df = pd.merge(df_inquiry, df_master[['id']], left_on='articleid_matched', right_on='id', how='inner')

# Tách y hệt như lúc train
_, test_df = train_test_split(merged_df, test_size=0.2, random_state=42)

# Lưu 20% này ra để kiểm thử
test_file_path = BASE_DIR / "preprocessed_data" / "unseen_test_data.csv"
test_df.to_csv(test_file_path, index=False)
print(f"Lưu thành công {len(test_df)} dòng test chưa được train vào {test_file_path}")