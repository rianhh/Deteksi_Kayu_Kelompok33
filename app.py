import streamlit as st
import numpy as np
import os
from PIL import Image
import subprocess
import pymysql
import cv2
import re
import base64
import bcrypt
from datetime import datetime
import io

# Path ke model yang dilatih
model_path = 'best_93_yoloDual.pt'
detect_dual_script_path = 'yolov9/detect_dual.py'

# Fungsi untuk koneksi ke database
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='deteksi_kayu',
        cursorclass=pymysql.cursors.DictCursor 
    )

# Koneksi ke database
conn = get_db_connection()
cursor = conn.cursor()

# Menyimpan data registrasi ke dalam database MySQL
def save_registration_data(username, email, password):
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    query = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
    values = (username, email, hashed_password)
    cursor.execute(query, values)
    conn.commit()

# Memverifikasi kredensial pengguna di database
def verify_credentials(username, password):
    query = "SELECT id, password FROM users WHERE username = %s"
    values = (username,)
    cursor.execute(query, values)
    result = cursor.fetchone()
    if result and bcrypt.checkpw(password.encode('utf-8'), result['password'].encode('utf-8')):
        st.session_state['user_id'] = result['id']
        return True
    return False


# Validasi email
def is_valid_email(email):
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(email_regex, email) is not None

# Validasi password
def is_valid_password(password):
    return any(c.isalpha() for c in password) and any(c.isdigit() for c in password)

# Menyimpan hasil deteksi ke dalam database
def save_detection_result(user_id, image_id, result_type, result_data):
    query = "INSERT INTO detection_results (user_id, image_id, result_type, result_data) VALUES (%s, %s, %s, %s)"
    values = (user_id, image_id, result_type, result_data)
    cursor.execute(query, values)
    conn.commit()

# Menyimpan informasi gambar ke dalam database
def save_image_info(user_id, image_type, image_data):
    query = "INSERT INTO images (user_id, image_type, image_data) VALUES (%s, %s, %s)"
    values = (user_id, image_type, image_data)
    cursor.execute(query, values)
    conn.commit()
    return cursor.lastrowid

# Menyimpan informasi analisis gambar ke dalam database
def save_image_analysis(user_id, username, image_path, input_image_id, output_image_id):
    query = "INSERT INTO image_analysis (user_id, username, image_path, input_image_id, output_image_id) VALUES (%s, %s, %s, %s, %s)"
    values = (user_id, username, image_path, input_image_id, output_image_id)
    cursor.execute(query, values)
    conn.commit()

# User Authentication
def login():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'register' not in st.session_state:
        st.session_state['register'] = False
    if 'username' not in st.session_state:
        st.session_state['username'] = ""

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("<h4>Login</h4>", unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
            login_button = st.form_submit_button("Login")

        if login_button:
            # Memverifikasi kredensial pengguna
            if verify_credentials(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.experimental_rerun()  # Rerun the app to update the state
            else:
                st.error("Invalid username atau password")
        
        st.markdown("Belum punya akun?")
        if st.button("Registrasi"):
            st.session_state['register'] = True
            st.experimental_rerun()

# User Registration
def register():
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("<h4>Buat akun</h4>", unsafe_allow_html=True)
        with st.form("register_form"):
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type='password')
            register_button = st.form_submit_button("Registrasi")

            if register_button:
                if not is_valid_email(email):
                    st.error("Format email tidak valid.")

                if not is_valid_password(password):
                    st.error("Password harus terdiri dari setidaknya satu huruf dan satu angka.")
                
                if username.strip() and email.strip() and password.strip() and is_valid_email(email) and is_valid_password(password):
                    # Menyimpan data registrasi ke dalam database
                    save_registration_data(username, email, password)
                    st.success("Registrasi berhasil. Silakan login.")
                    st.session_state['register'] = False
                else:
                    st.error("Terdapat kesalahan dalam registrasi. Pastikan semua field terisi dengan benar.")

        if st.button("Kembali ke Login"):
            st.session_state['register'] = False
            st.experimental_rerun()

# Main app
def main(): 
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'register' not in st.session_state:
        st.session_state['register'] = False

    # Center the title
    st.markdown(
        f"""
        <h1 style='text-align: center;'>Deteksi Kayu Layak Guna</h1>
        """,
        unsafe_allow_html=True
    )

    # Sidebar for Login/Registration
    if not st.session_state['logged_in']:
        if st.session_state['register']:
            register()
        else:
            login()
    else:
        st.sidebar.title("Navigasi")
        if st.sidebar.button('Deteksi', key='deteksi'):
            st.session_state.selected_tab = "Deteksi"
        if st.sidebar.button('Riwayat Gambar', key='riwayat'):
            st.session_state.selected_tab = "Riwayat Gambar"

        if "selected_tab" not in st.session_state:
            st.session_state.selected_tab = "Deteksi"

        if st.session_state.selected_tab == 'Deteksi':
            st.header('Deteksi Kayu Layak Guna')
            st.write('Aplikasi ini akan menganalisis apakah kayu "bagus" atau "buruk" berdasarkan gambar yang Anda unggah.')
            uploaded_file = st.file_uploader("Pilih gambar kayu untuk dianalisis", type=["jpg", "jpeg", "png"])

            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                st.image(image, caption='Gambar Kayu yang Diupload', use_column_width=True)

                # Save input image to database
                with io.BytesIO() as output:
                    image.save(output, format="PNG")
                    image_binary = output.getvalue()

                image_type = "image"
                user_id = st.session_state['user_id']
                input_image_id = save_image_info(user_id, image_type, image_binary)

                image_path = f'{input_image_id}.png'

                with open(image_path, 'wb') as f:
                    f.write(image_binary)

                if st.button('Deteksi'):
                    with st.spinner('Proses deteksi sedang berjalan...'):
                        result = subprocess.run(['python', detect_dual_script_path, '--weights', model_path, '--img', '640', '--conf', '0.1', '--source', image_path, '--project', '.', '--name', f'output_{input_image_id}', '--exist-ok'], capture_output=True, text=True)

                        detected_image_path = f'output_{input_image_id}/{image_path}'

                        if os.path.exists(detected_image_path):
                            # Load and display detected image
                            result_image = Image.open(detected_image_path)
                            st.image(result_image, caption='Hasil Deteksi', use_column_width=True)

                            # Save detected image to database
                            with open(detected_image_path, 'rb') as f:
                                result_image_binary = f.read()
                            result_type = "image"
                            output_image_id = save_detection_result(user_id, input_image_id, result_type, result_image_binary)

                            # Save image analysis to database
                            save_image_analysis(user_id, st.session_state['username'], image_path, input_image_id, output_image_id)

                            # Display wood quality information
                            st.markdown(
                                f"""
                                <div style='display: flex; justify-content: space-around; margin-top: 20px;'>
                                    <div style='background-color: #4CAF50; color: white; padding: 10px; border-radius: 10px; box-shadow: 2px 2px 5px grey; flex: 1; text-align: center;'>
                                        <h3 style='font-family: Arial Black, sans-serif;'>Kondisi Kayu Berkualitas</h3>
                                        <p>Jika jumlah kotak deteksi terbatas, maka kemungkinan besar kayu tersebut berkualitas baik.</p>
                                    </div>
                                    <div style='background-color: #ff4d4d; color: white; padding: 10px; border-radius: 10px; box-shadow: 2px 2px 5px grey; flex: 1; text-align: center;'>
                                        <h3 style='font-family: Arial Black, sans-serif;'>Kondisi Kayu Bermasalah</h3>
                                        <p>Apabila jumlah kotak deteksi banyak, dapat diprediksi bahwa kayu tersebut memiliki kualitas yang kurang baik.</p>
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            # Remove input image after processing
                            os.remove(image_path)

                        else:
                            st.error('Folder hasil deteksi tidak ditemukan.')

        elif st.session_state.selected_tab == 'Riwayat Gambar':
            st.title('Riwayat Gambar')

            # Mengambil user_id dari session state
            user_id = st.session_state['user_id']

            # Fetch image log dari database untuk user saat ini
            query = """
            SELECT images.id AS image_id, images.created_at AS image_created_at, detection_results.result_data 
            FROM images 
            LEFT JOIN detection_results ON images.id = detection_results.image_id 
            LEFT JOIN image_analysis ON images.id = image_analysis.input_image_id 
            WHERE images.user_id = %s 
            ORDER BY images.created_at DESC
            """
            cursor.execute(query, (user_id,))
            image_log = cursor.fetchall()

            # Tampilkan image log
            if not image_log:
                 st.write('Belum ada hasil deteksi yang tersedia.')
            else:
              deteksi_count = 0
              for result_data in image_log:
               if result_data['result_data'] is not None:
                deteksi_count += 1
                st.write(f'**Hasil Deteksi {deteksi_count}:**')
                result_image = Image.open(io.BytesIO(result_data['result_data']))
                st.image(result_image, caption=f'Hasil Deteksi (ID: {result_data["image_id"]}, Waktu: {result_data["image_created_at"]})', use_column_width=True)
        # Logout Button
        st.sidebar.markdown("---")
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.experimental_rerun()

if __name__ == "__main__":
    st.set_page_config(page_title="Deteksi Kayu Layak Guna", page_icon="🪵", layout="wide", initial_sidebar_state="expanded")
    main()
