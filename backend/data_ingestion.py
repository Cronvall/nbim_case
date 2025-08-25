"""
Data ingestion module for loading and normalizing NBIM and custody CSV files.
"""
import pandas as pd
from typing import Tuple, Dict, Any
import os


class DataIngestion:
    """Handles loading and normalizing dividend data from CSV files."""
    
    def __init__(self, data_dir: str = "../data"):
        self.data_dir = data_dir
        
    def load_nbim_data(self, filename: str = "NBIM_Dividend_Bookings 1.csv") -> pd.DataFrame:
        """Load NBIM dividend bookings data."""
        filepath = os.path.join(self.data_dir, filename)
        df = pd.read_csv(filepath, sep=';')
        return self._normalize_nbim_data(df)
    
    def load_custody_data(self, filename: str = "CUSTODY_Dividend_Bookings 1.csv") -> pd.DataFrame:
        """Load custody dividend bookings data."""
        filepath = os.path.join(self.data_dir, filename)
        df = pd.read_csv(filepath, sep=';')
        return self._normalize_custody_data(df)
    
    def _normalize_nbim_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize NBIM data to common format."""
        normalized = pd.DataFrame()
        
        # Map to common column names
        normalized['event_key'] = df['COAC_EVENT_KEY']
        normalized['isin'] = df['ISIN']
        normalized['sedol'] = df['SEDOL']
        normalized['ticker'] = df['TICKER']
        normalized['company_name'] = df['ORGANISATION_NAME']
        normalized['ex_date'] = pd.to_datetime(df['EXDATE'], format='%d.%m.%Y')
        normalized['payment_date'] = pd.to_datetime(df['PAYMENT_DATE'], format='%d.%m.%Y')
        normalized['dividend_rate'] = df['DIVIDENDS_PER_SHARE']
        normalized['nominal_basis'] = df['NOMINAL_BASIS']
        normalized['gross_amount'] = df['GROSS_AMOUNT_QUOTATION']
        normalized['net_amount'] = df['NET_AMOUNT_QUOTATION']
        normalized['tax_amount'] = df['WTHTAX_COST_QUOTATION']
        normalized['tax_rate'] = df['WTHTAX_RATE']
        normalized['currency'] = df['QUOTATION_CURRENCY']
        normalized['custodian'] = df['CUSTODIAN']
        normalized['bank_account'] = df['BANK_ACCOUNT']
        normalized['source'] = 'NBIM'
        
        return normalized
    
    def _normalize_custody_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize custody data to common format."""
        normalized = pd.DataFrame()
        
        # Map to common column names
        normalized['event_key'] = df['COAC_EVENT_KEY']
        normalized['isin'] = df['ISIN']
        normalized['sedol'] = df['SEDOL']
        normalized['ticker'] = None  # Not available in custody data
        normalized['company_name'] = None  # Not available in custody data
        normalized['ex_date'] = pd.to_datetime(df['EX_DATE'], format='%d.%m.%Y')
        normalized['payment_date'] = pd.to_datetime(df['PAY_DATE'], format='%d.%m.%Y')
        normalized['dividend_rate'] = df['DIV_RATE']
        normalized['nominal_basis'] = df['NOMINAL_BASIS']
        normalized['gross_amount'] = df['GROSS_AMOUNT']
        normalized['net_amount'] = df['NET_AMOUNT_QC']
        normalized['tax_amount'] = df['TAX']
        normalized['tax_rate'] = df['TAX_RATE']
        normalized['currency'] = df['CURRENCIES'].str.split().str[0]  # Take first currency
        normalized['custodian'] = df['CUSTODIAN']
        normalized['bank_account'] = df['BANK_ACCOUNTS']
        normalized['source'] = 'CUSTODY'
        
        return normalized
    
    def load_all_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load both NBIM and custody data."""
        nbim_data = self.load_nbim_data()
        custody_data = self.load_custody_data()
        return nbim_data, custody_data
