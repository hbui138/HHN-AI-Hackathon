import os
import glob
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import warnings

# Ignore warnings for cleaner output
warnings.filterwarnings('ignore')

def main():
    # 1. Define paths
    BASE_DIR = Path(__file__).resolve().parent.parent
    master_db_path = BASE_DIR / "preprocessed_data" / "master_database.parquet"
    inquiry_dir = BASE_DIR / "customerinquiry"
    model_output_path = BASE_DIR / "models" / "finetuned_boie_minilm"
    
    # Create models directory if it does not exist
    model_output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Loading datasets...")
    
    # 2. Load the master database to get the combined_text for each product ID
    try:
        df_master = pd.read_parquet(master_db_path)
        # Keep only necessary columns to save memory
        df_master = df_master[['id', 'combined_text']].copy()
        # Ensure ID is string for merging
        df_master['id'] = df_master['id'].astype(str).str.strip()
    except FileNotFoundError:
        print(f"Error: Master database not found at {master_db_path}")
        return

    # 3. Load all customer inquiry CSV files
    inquiry_files = glob.glob(str(inquiry_dir / "*.csv"))
    if not inquiry_files:
        print(f"Error: No CSV files found in {inquiry_dir}")
        return

    df_inquiries_list = []
    for file in inquiry_files:
        # on_bad_lines='skip' helps bypass malformed rows in raw CSVs
        df = pd.read_csv(file, on_bad_lines='skip', engine='python')
        df_inquiries_list.append(df)
        
    df_inquiry = pd.concat(df_inquiries_list, ignore_index=True)

    # 4. Clean and prepare data for merging
    # Drop rows without an assigned article ID or query
    df_inquiry = df_inquiry.dropna(subset=['articleid_matched', 'CustomerArticleDescription'])
    
    # Clean the articleid_matched (handle float parsing issues like '10004471.0')
    df_inquiry['articleid_matched'] = pd.to_numeric(df_inquiry['articleid_matched'], errors='coerce')
    df_inquiry = df_inquiry.dropna(subset=['articleid_matched'])
    df_inquiry['articleid_matched'] = df_inquiry['articleid_matched'].astype(int).astype(str).str.strip()

    # Rename columns for easier merging
    df_inquiry = df_inquiry.rename(columns={'CustomerArticleDescription': 'query'})

    # 5. Merge query data with target product descriptions
    merged_df = pd.merge(
        df_inquiry, 
        df_master, 
        left_on='articleid_matched', 
        right_on='id', 
        how='inner'
    )
    
    print(f"Successfully matched {len(merged_df)} query-product pairs for training.")
    
    if len(merged_df) == 0:
        print("No matching records found. Check ID formats in CSV and Master DB.")
        return

    # 6. Prepare training and validation datasets (80/20 split)
    # The MNRL loss function requires positive pairs (query, positive_document)
    # The batch itself provides the negative documents inherently
    train_df, val_df = train_test_split(merged_df, test_size=0.2, random_state=42)
    
    train_examples = []
    for _, row in train_df.iterrows():
        train_examples.append(InputExample(texts=[str(row['query']), str(row['combined_text'])]))
        
    val_examples = []
    for _, row in val_df.iterrows():
        val_examples.append(InputExample(texts=[str(row['query']), str(row['combined_text'])]))

    print(f"Training pairs: {len(train_examples)} | Validation pairs: {len(val_examples)}")

    # 7. Initialize model and data loader
    model_name = 'all-MiniLM-L6-v2'
    print(f"Loading base model: {model_name}...")
    model = SentenceTransformer(model_name)
    model.max_seq_length = 128

    # Use a batch size of 16 or 32 depending on your machine's RAM/VRAM
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
    
    # MultipleNegativesRankingLoss is the state-of-the-art for this exact task
    train_loss = losses.MultipleNegativesRankingLoss(model=model)

    # 8. Start Fine-tuning
    num_epochs = 1
    print(f"Starting training for {num_epochs} epochs...")
    
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=num_epochs,
        warmup_steps=100,
        output_path=str(model_output_path),
        show_progress_bar=True,
        use_amp=True
    )

    print(f"\nModel successfully fine-tuned and saved to: {model_output_path}")

if __name__ == "__main__":
    main()