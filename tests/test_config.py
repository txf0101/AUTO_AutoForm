from pathlib import Path

from autoform_agent.config import get_logging_config, get_queue_config, get_remote_hosts


CONFIG_XML = """<Configuration version="R13">
  <QueuingConfiguration>
    <queuingOnlyHost>false</queuingOnlyHost>
    <queue key="1">
      <QueueName>Queue1</QueueName>
      <MaxJobs>1</MaxJobs>
      <LicenseServer>2375@localhost</LicenseServer>
      <RestrictToParallelSolver>0</RestrictToParallelSolver>
      <RestrictQueuingOptions>QueueToTop</RestrictQueuingOptions>
    </queue>
  </QueuingConfiguration>
  <RemoteComputingConfiguration>
    <useAutoConfig>false</useAutoConfig>
    <autoConfigURL></autoConfigURL>
    <HostAndJobsConfiguration>
      <host key="Localhost">
        <name>Localhost</name>
        <host>localhost</host>
        <port>865</port>
        <parallelOption>-1</parallelOption>
        <module>
          <item>Sigma</item>
          <item>Trim</item>
          <item>Solver</item>
          <item>Compensation</item>
        </module>
      </host>
    </HostAndJobsConfiguration>
    <kinCheckOnLocalhost>false</kinCheckOnLocalhost>
    <defaultHost></defaultHost>
  </RemoteComputingConfiguration>
  <LoggingConfiguration>
    <logLevel>info</logLevel>
    <compressLogs>true</compressLogs>
    <automaticLogCollectionLevel>Failed</automaticLogCollectionLevel>
  </LoggingConfiguration>
</Configuration>
"""


def test_get_queue_config_reads_queues(tmp_path: Path) -> None:
    config = tmp_path / "systemConfigFile.xml"
    config.write_text(CONFIG_XML, encoding="utf-8")

    result = get_queue_config(config_path=config)

    assert result["queuing_only_host"] is False
    assert result["queues"] == [
        {
            "key": "1",
            "name": "Queue1",
            "max_jobs": 1,
            "license_server": "2375@localhost",
            "restrict_to_parallel_solver": 0,
            "restrict_queuing_options": "QueueToTop",
        }
    ]


def test_get_remote_hosts_reads_modules(tmp_path: Path) -> None:
    config = tmp_path / "systemConfigFile.xml"
    config.write_text(CONFIG_XML, encoding="utf-8")

    result = get_remote_hosts(config_path=config)

    assert result["use_auto_config"] is False
    assert result["hosts"][0]["modules"] == ["Sigma", "Trim", "Solver", "Compensation"]
    assert result["hosts"][0]["port"] == 865


def test_get_logging_config_reads_values(tmp_path: Path) -> None:
    config = tmp_path / "systemConfigFile.xml"
    config.write_text(CONFIG_XML, encoding="utf-8")

    result = get_logging_config(config_path=config)

    assert result["values"]["logLevel"] == "info"
    assert result["values"]["automaticLogCollectionLevel"] == "Failed"
