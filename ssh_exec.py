import paramiko
import sys
import io

HOST = "91.99.52.156"
USER = "root"
PASS = "psAEvwi3miCgdgWucMcf"


def upload_file(local_path, remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=15)
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()
    print(f"Uploaded {local_path} -> {remote_path}")


def run_commands(commands):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=15)

    for cmd in commands:
        print(f"\n{'=' * 60}")
        print(f"RUNNING: {cmd}")
        print("=" * 60)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=300)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out:
            sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
            sys.stdout.buffer.flush()
        if err:
            sys.stderr.buffer.write(err.encode("utf-8", errors="replace"))
            sys.stderr.buffer.flush()
        print(f"\nEXIT CODE: {exit_code}")
        if exit_code != 0:
            print(f"WARNING: Command failed with exit code {exit_code}")

    client.close()


if __name__ == "__main__":
    run_commands(sys.argv[1:])
