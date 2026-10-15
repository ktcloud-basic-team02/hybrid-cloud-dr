-- MySQL dump 10.13  Distrib 8.4.11, for Linux (x86_64)
--
-- Host: localhost    Database: shop
-- ------------------------------------------------------
-- Server version       8.4.11

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Dumping data for table `products`
--

/*!40000 ALTER TABLE `products` DISABLE KEYS */;
INSERT INTO `products` (`id`, `brand`, `name`, `notes`, `size_ml`, `price`, `stock`, `limited`, `image_url`, `pos`) VALUES (1,'BEAVER','Ambre Solaire','Amber · Vanilla · Sandalwood',50,128000,30,0,'img/p1.jpg','50% 62%'),(2,'PRADA','Paradoxe','Neroli · Pink Pear · Amber',50,156000,30,0,'img/p2.jpg','50% 60%'),(3,'MORRA','1st Collection','Rose · Cedar · Clove · Tonka',50,98000,30,0,'img/p3.jpg','50% 50%'),(4,'CHANEL','Coco Mademoiselle Intense','Orange · Rose · Patchouli',50,198000,30,0,'img/p5.jpg','50% 50%'),(5,'CLIVE CHRISTIAN','Town & Country','Frankincense · Amber · Spice',50,420000,1,1,'img/p6.jpg','55% 50%'),(6,'NISHANE','Ani','Vanilla · Ginger · Cardamom',50,215000,30,0,'img/p7.jpg','45% 50%');
/*!40000 ALTER TABLE `products` ENABLE KEYS */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-15 14:08:59