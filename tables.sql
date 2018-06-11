
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

--
-- Table structure for table `ACCOUNTS`
--

CREATE TABLE `ACCOUNTS` (
  `UID` bigint(20) NOT NULL,
  `ACCOUNT` varchar(50) NOT NULL,
  `ADDED` bigint(20) NOT NULL,
  `UPDATED` bigint(20) NOT NULL,
  `VOTED` bigint(20) NOT NULL,
  `WITNESS_VOTES_INIT` int(11) NOT NULL,
  `WITNESS_VOTES_UPDATE` int(11) NOT NULL,
  `STEEM_POWER` float NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `LAST_BLOCK`
--

CREATE TABLE `LAST_BLOCK` (
  `UID` int(11) NOT NULL,
  `NUM` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Dumping data for table `LAST_BLOCK`
--

INSERT INTO `LAST_BLOCK` (`UID`, `NUM`) VALUES
(1, 23228619);

--
-- Table structure for table `TAGGED`
--

CREATE TABLE `TAGGED` (
  `UID` bigint(20) NOT NULL,
  `TIMESTAMP` bigint(20) NOT NULL,
  `AUTHOR` varchar(50) NOT NULL,
  `PERMLINK` varchar(1000) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Table structure for table `VOTES`
--

CREATE TABLE `VOTES` (
  `UID` bigint(20) NOT NULL,
  `TIMESTAMP` bigint(20) NOT NULL,
  `AUTHOR` varchar(50) NOT NULL,
  `PERMLINK` varchar(1000) NOT NULL,
  `WEIGHT` float NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `ACCOUNTS`
--
ALTER TABLE `ACCOUNTS`
  ADD PRIMARY KEY (`UID`),
  ADD UNIQUE KEY `ACCOUNT` (`ACCOUNT`);

--
-- Indexes for table `TAGGED`
--
ALTER TABLE `TAGGED`
  ADD PRIMARY KEY (`UID`);

--
-- Indexes for table `VOTES`
--
ALTER TABLE `VOTES`
  ADD PRIMARY KEY (`UID`);

