# Copyright (c) 2025, DAS and contributors
# For license information, please see license.txt

def format_nomor_telepon(nomor_telepon):
    if nomor_telepon.startswith('0'):
        return '62' + nomor_telepon[1:]
    
    return nomor_telepon