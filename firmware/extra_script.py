Import("env")

# PlatformIO pre-build helper script
print("Executing pre-build configuration for Nigerian Solar Gateway...")
# Can inject build flags or git hash if required
env.Append(
    CPPDEFINES=[
        ("BUILD_TIMESTAMP", str(int(env.get("UNIX_TIME", 0))))
    ]
)
