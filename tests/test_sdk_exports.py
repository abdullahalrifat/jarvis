def test_public_sdk_resolves_hardened_cloud_types_lazily():
    from jarvis_cli.sdk import CloudWorker, RemoteJarvis

    assert CloudWorker.__name__ == "FencedCloudWorker"
    assert RemoteJarvis.__name__ == "AutonomousRemoteJarvis"
