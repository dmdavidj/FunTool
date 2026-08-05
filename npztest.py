import numpy as np

# 분석할 파일 경로
NPZ_PATH = 'AAA.npz'

def inspect_npz_file():
    try:
        # 파일 로드 (allow_pickle=True 필수)
        with np.load(NPZ_PATH, allow_pickle=True) as data:
            print(f"=== [{NPZ_PATH}] 파일 분석 결과 ===")
            
            # 1. RMS 오차 확인 (가장 중요)
            if 'rms' in data:
                rms = data['rms']
                print(f"\n1. RMS 오차 (재투영 오차): {rms:.4f} pixels")
                if rms < 0.5:
                    print("   -> 판정: [최상] 매우 정밀합니다.")
                elif rms < 1.0:
                    print("   -> 판정: [양호] 사용할 수 있습니다.")
                else:
                    print("   -> 판정: [실패] 오차가 너무 큽니다. 재작업 필수!")
            else:
                print("\n1. RMS 데이터가 없습니다. (직접 계산 필요)")

            # 2. 카메라 매트릭스 확인 (중심점)
            if 'cameraMatrix' in data:
                mtx = data['cameraMatrix']
                cx, cy = mtx[0, 2], mtx[1, 2]
                fx, fy = mtx[0, 0], mtx[1, 1]
                print(f"\n2. 카메라 내부 파라미터")
                print(f"   - 초점거리(fx, fy): {fx:.2f}, {fy:.2f}")
                print(f"   - 광학중심(cx, cy): {cx:.2f}, {cy:.2f}")
                # 해상도 정보가 있다면 중앙인지 비교 가능
                if 'image_size' in data:
                    w, h = data['image_size']
                    print(f"   - 이미지 해상도   : {w} x {h}")
                    if abs(cx - w/2) > 50 or abs(cy - h/2) > 50:
                        print("   -> 경고: 중심점이 이미지 중앙에서 너무 많이 벗어났습니다.")
            
            # 3. 경고 메시지 확인
            if 'warnings' in data:
                warnings = data['warnings']
                print(f"\n3. ⚠️ 저장된 경고 메시지!!")
                print(f"   -> {warnings}")
            
            # 4. 왜곡 계수 확인
            if 'distCoeffs' in data:
                dist = data['distCoeffs']
                print(f"\n4. 왜곡 계수 개수: {dist.shape[1]}개")
                if dist.shape[1] > 8:
                    print("   -> 참고: 매우 복잡한 왜곡 모델을 사용했습니다. (과적합 주의)")

    except FileNotFoundError:
        print("파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"파일을 읽는 중 오류 발생: {e}")

if __name__ == "__main__":
    inspect_npz_file()