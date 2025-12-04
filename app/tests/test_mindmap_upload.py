"""
Test script để upload ảnh vào MinIO và verify
Không cần gọi Gemini API, dùng ảnh có sẵn
"""

import os
from PIL import Image

from app.services.minio_client import minio_client


def test_upload_image_to_minio():
    """Test upload ảnh vào MinIO"""

    # Test parameters
    test_image_path = "/home/hungmanh/Documents/CodeMentor/app/data/images/7d596b44-309a-407a-b5bb-cd7066bab598-01.jpg"
    test_session_id = "test_session_123"

    print(f"\n{'=' * 80}")
    print("🧪 Testing Image Upload to MinIO")
    print(f"{'=' * 80}\n")

    # 1. Check if test image exists
    if not os.path.exists(test_image_path):
        print(f"❌ Test image not found: {test_image_path}")
        return False

    file_size = os.path.getsize(test_image_path)
    print(f"✅ Found test image: {test_image_path}")
    print(f"📦 File size: {file_size} bytes ({file_size / 1024:.2f} KB)")

    # 2. Load and verify image
    try:
        img = Image.open(test_image_path)
        print(f"🖼️ Image loaded: {img.size}, {img.format}, {img.mode}")
    except Exception as e:
        print(f"❌ Failed to load image: {e}")
        return False

    # 3. Save to temp file (simulate Gemini output)
    import tempfile

    temp_path = os.path.join(tempfile.gettempdir(), f"mind_map_{test_session_id}.png")

    try:
        img.save(temp_path, format="PNG")
        temp_size = os.path.getsize(temp_path)
        print(f"✅ Saved to temp: {temp_path} ({temp_size} bytes)")
    except Exception as e:
        print(f"❌ Failed to save temp file: {e}")
        return False

    # 4. Upload to MinIO
    minio_path = f"{test_session_id}/mind_map.png"
    print(f"\n📤 Uploading to MinIO: {minio_path}")

    try:
        with open(temp_path, "rb") as f:
            file_data = f.read()
            print(f"📦 File data size: {len(file_data)} bytes")
            print(f"📦 File data type: {type(file_data)}")

            minio_client.upload_data(minio_path, file_data)
            print("✅ Upload completed!")

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 5. Verify upload
    print("\n🔍 Verifying upload...")

    try:
        if minio_client.file_exists(minio_path):
            print(f"✅ File exists on MinIO: {minio_path}")

            # Try to download back
            downloaded_data = minio_client.download_data(minio_path)
            if downloaded_data:
                print(f"✅ Successfully downloaded back: {len(downloaded_data)} bytes")

                # Verify data integrity
                if len(downloaded_data) == len(file_data):
                    print("✅ Data integrity verified (size match)")
                else:
                    print(
                        f"⚠️ Size mismatch: uploaded={len(file_data)}, downloaded={len(downloaded_data)}"
                    )

                # Save downloaded image to verify
                verify_path = "/home/hungmanh/Documents/CodeMentor/app/data/downloaded_mind_map.png"
                with open(verify_path, "wb") as f:
                    f.write(downloaded_data)
                print(f"✅ Downloaded image saved to: {verify_path}")

            else:
                print("❌ Download failed!")
                return False
        else:
            print(f"❌ File does not exist on MinIO: {minio_path}")
            return False

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 6. List all files in session folder
    print("\n📁 Listing all files in session folder:")
    try:
        files = minio_client.list_files(prefix=f"{test_session_id}/")
        if files:
            for file in files:
                print(f"   - {file}")
        else:
            print("   (No files found)")
    except Exception as e:
        print(f"❌ Failed to list files: {e}")

    # 7. Clean up temp file
    if os.path.exists(temp_path):
        os.remove(temp_path)
        print(f"\n🗑️ Removed temp file: {temp_path}")

    print(f"\n{'=' * 80}")
    print("🎉 Test completed successfully!")
    print(f"{'=' * 80}\n")

    print("📝 Summary:")
    print(f"   - Session ID: {test_session_id}")
    print(f"   - MinIO path: {minio_path}")
    print(f"   - File size: {len(file_data)} bytes")
    print("   - Status: ✅ SUCCESS")

    return True


if __name__ == "__main__":
    # Chỉ test upload, không test API
    test_upload_image_to_minio()
